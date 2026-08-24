from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from packages.sheets import SheetWrapper

from ..auth import AuthUser, get_current_user, sign_session_token
from ..config import Settings, get_settings
from ..dependencies import get_sheet_wrapper
from ..models import LoginCodeRequest, LoginCodeResponse, LoginRequest, LoginVerifyRequest, SessionResponse
from ..services.common import generate_auth_code, hash_auth_code, phones_match
from ..services.otp_delivery import deliver_login_code
from ..services.pilot import get_pilot_boat_id


router = APIRouter(prefix="/auth", tags=["auth"])
_VERIFY_FAILS: dict[str, list[datetime]] = {}


def _set_session_cookie(response: Response, *, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")


def _session_payload(user: dict[str, str], *, boat_id: str | None = None) -> dict[str, str]:
    payload = {
        "staff_user_id": user["staff_user_id"],
        "role": user["role"],
        "full_name": user.get("full_name", ""),
        "club_id": user.get("club_id", ""),
        "phone": user.get("phone", ""),
    }
    if boat_id:
        payload["boat_id"] = boat_id
    return payload


def _session_response(user: dict[str, str], *, boat_id: str | None = None, token: str | None = None) -> SessionResponse:
    return SessionResponse(
        staff_user_id=user["staff_user_id"],
        role=user["role"],
        full_name=user.get("full_name", ""),
        club_id=user.get("club_id", ""),
        phone=user.get("phone", ""),
        boat_id=boat_id,
        token=token,
    )


def _is_active(user: dict[str, str]) -> bool:
    return str(user.get("is_active", "")).lower() in {"1", "true", "yes"}


def _resolve_staff_user(
    sheet: SheetWrapper,
    *,
    staff_user_id: str | None,
    phone: str | None,
) -> dict[str, str]:
    users = [row for row in sheet.read_tab("staff_users") if _is_active(row)]
    identity_id = (staff_user_id or "").strip()
    identity_phone = (phone or "").strip()
    if identity_phone and "@" in identity_phone:
        identity_id = identity_id or identity_phone
        identity_phone = ""

    if identity_id:
        users = [
            row
            for row in users
            if row.get("staff_user_id") == identity_id or str(row.get("staff_user_id", "")).lower() == identity_id.lower()
        ]
    if identity_phone:
        users = [row for row in users if phones_match(str(row.get("phone", "")), identity_phone)]
    if not identity_id and not identity_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="staff_user_id or phone is required")
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Several staff records match this phone. Enter staff ID.",
        )
    return users[0]


def _check_verify_rate(staff_user_id: str, settings: Settings) -> None:
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=settings.auth_code_rate_limit_window_seconds)
    attempts = [stamp for stamp in _VERIFY_FAILS.get(staff_user_id, []) if now - stamp <= window]
    _VERIFY_FAILS[staff_user_id] = attempts
    max_attempts = max(settings.auth_code_rate_limit_max_attempts * 4, 10)
    if len(attempts) >= max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")


def _record_verify_fail(staff_user_id: str) -> None:
    _VERIFY_FAILS.setdefault(staff_user_id, []).append(datetime.now(timezone.utc))


@router.post("/request-code", response_model=LoginCodeResponse)
def request_login_code(
    payload: LoginCodeRequest,
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> LoginCodeResponse:
    user = _resolve_staff_user(sheet, staff_user_id=payload.staff_user_id, phone=payload.phone)
    staff_user_id = user["staff_user_id"]

    now = datetime.now(timezone.utc)
    threshold = (now - timedelta(seconds=settings.auth_code_rate_limit_window_seconds)).isoformat()
    recent_codes = [
        row
        for row in sheet.read_tab("auth_codes")
        if row.get("staff_user_id") == staff_user_id and row.get("created_at", "") >= threshold
    ]
    if len(recent_codes) >= settings.auth_code_rate_limit_max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login code requests")

    code = generate_auth_code()
    delivery_channel = deliver_login_code(code=code, telegram_id=str(user.get("telegram_id") or ""))
    auth_code_id = f"auth-{uuid4()}"
    row = {
        "auth_code_id": auth_code_id,
        "staff_user_id": staff_user_id,
        "club_id": user.get("club_id", ""),
        "code_hash": hash_auth_code(settings.session_secret, staff_user_id, code),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=settings.auth_code_ttl_seconds)).isoformat(),
        "used_at": "",
        "delivery_channel": delivery_channel,
    }
    sheet.append_row("auth_codes", row, unique_key="auth_code_id")
    sheet.write_audit(
        action="request_login_code",
        entity="auth",
        entity_id=staff_user_id,
        diff_json={"delivery_channel": delivery_channel, "auth_code_id": auth_code_id},
        actor=staff_user_id,
    )
    return LoginCodeResponse(
        delivery_channel=delivery_channel,
        expires_in_seconds=settings.auth_code_ttl_seconds,
        debug_code=code if settings.debug_auth_codes_in_response else None,
        staff_user_id=staff_user_id,
        full_name=user.get("full_name") or None,
    )


@router.post("/verify-code", response_model=SessionResponse)
def verify_login_code(
    payload: LoginVerifyRequest,
    response: Response,
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    user = _resolve_staff_user(sheet, staff_user_id=payload.staff_user_id, phone=payload.phone)
    staff_user_id = user["staff_user_id"]
    _check_verify_rate(staff_user_id, settings)

    now_iso = datetime.now(timezone.utc).isoformat()
    expected_hash = hash_auth_code(settings.session_secret, staff_user_id, payload.code)
    matching_row = None
    for row in reversed(sheet.read_tab("auth_codes")):
        if row.get("staff_user_id") != staff_user_id:
            continue
        if row.get("used_at"):
            continue
        if row.get("expires_at", "") < now_iso:
            continue
        if row.get("code_hash") == expected_hash:
            matching_row = row
            break

    if matching_row is None:
        _record_verify_fail(staff_user_id)
        sheet.write_audit(
            action="verify_login_code_failed",
            entity="auth",
            entity_id=staff_user_id,
            diff_json={"reason": "invalid_or_expired_code"},
            actor=staff_user_id,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired code")

    _VERIFY_FAILS.pop(staff_user_id, None)
    sheet.update_by_id(
        "auth_codes",
        "auth_code_id",
        matching_row["auth_code_id"],
        {"used_at": now_iso},
        actor=staff_user_id,
        audit_entity="auth_code",
    )

    boat_id = get_pilot_boat_id(sheet, staff_user_id=user["staff_user_id"], club_id=user.get("club_id", ""))
    token = sign_session_token(settings, _session_payload(user, boat_id=boat_id))
    _set_session_cookie(response, settings=settings, token=token)
    sheet.write_audit(
        action="login_success",
        entity="auth",
        entity_id=staff_user_id,
        diff_json={"boat_id": boat_id or ""},
        actor=staff_user_id,
    )
    return _session_response(user, boat_id=boat_id, token=token)


@router.get("/me", response_model=SessionResponse)
def me(
    user: AuthUser = Depends(get_current_user),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    boat_id = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id)
    token = sign_session_token(
        settings,
        _session_payload(
            {
                "staff_user_id": user.staff_user_id,
                "role": user.role,
                "full_name": user.full_name,
                "club_id": user.club_id,
                "phone": user.phone,
            },
            boat_id=boat_id,
        ),
    )
    return SessionResponse(
        staff_user_id=user.staff_user_id,
        role=user.role,
        full_name=user.full_name,
        club_id=user.club_id,
        phone=user.phone,
        boat_id=boat_id,
        token=token,
    )


@router.post("/logout")
def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _clear_session_cookie(response, settings)
    return {"status": "ok"}


@router.post("/login", response_model=SessionResponse)
def legacy_login(
    payload: LoginRequest,
    response: Response,
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    if not settings.allow_legacy_staff_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Legacy login is disabled. Use request-code/verify-code flow.",
        )
    if settings.environment == "production":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Legacy login is disabled in production")

    users = sheet.find("staff_users", {"staff_user_id": payload.staff_user_id})
    user = next((item for item in users if _is_active(item)), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    boat_id = get_pilot_boat_id(sheet, staff_user_id=user["staff_user_id"], club_id=user.get("club_id", ""))
    token = sign_session_token(settings, _session_payload(user, boat_id=boat_id))
    _set_session_cookie(response, settings=settings, token=token)
    return _session_response(user, boat_id=boat_id, token=token)
