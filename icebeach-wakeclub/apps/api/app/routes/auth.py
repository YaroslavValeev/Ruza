from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from packages.sheets import SheetWrapper

from ..auth import AuthUser, get_current_user, sign_session_token
from ..config import Settings, get_settings
from ..dependencies import get_sheet_wrapper
from ..models import LoginCodeRequest, LoginCodeResponse, LoginRequest, LoginVerifyRequest, SessionResponse
from ..services.common import generate_auth_code, hash_auth_code, normalize_phone, parse_utc_instant, phones_match
from ..services.pilot import get_pilot_boat_id


router = APIRouter(prefix="/auth", tags=["auth"])


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


def _session_response(user: dict[str, str], *, boat_id: str | None = None) -> SessionResponse:
    return SessionResponse(
        staff_user_id=user["staff_user_id"],
        role=user["role"],
        full_name=user.get("full_name", ""),
        club_id=user.get("club_id", ""),
        phone=user.get("phone", ""),
        boat_id=boat_id,
    )


@router.post("/request-code", response_model=LoginCodeResponse)
def request_login_code(
    payload: LoginCodeRequest,
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> LoginCodeResponse:
    users = sheet.find("staff_users", {"staff_user_id": payload.staff_user_id})
    user = next((u for u in users if str(u.get("is_active", "")).lower() in {"1", "true", "yes"}), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    expected_phone = user.get("phone", "")
    if not phones_match(expected_phone, payload.phone):
        sheet.write_audit(
            action="request_login_code_failed",
            entity="auth",
            entity_id=payload.staff_user_id,
            diff_json={"reason": "phone_mismatch"},
            actor=payload.staff_user_id,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phone does not match staff record")

    now = datetime.now(timezone.utc)
    threshold = (now - timedelta(seconds=settings.auth_code_rate_limit_window_seconds)).isoformat()
    recent_codes = [
        row
        for row in sheet.read_tab("auth_codes")
        if row.get("staff_user_id") == payload.staff_user_id and row.get("created_at", "") >= threshold
    ]
    if len(recent_codes) >= settings.auth_code_rate_limit_max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login code requests")

    code = generate_auth_code()
    auth_code_id = f"auth-{uuid4()}"
    row = {
        "auth_code_id": auth_code_id,
        "staff_user_id": payload.staff_user_id,
        "club_id": user.get("club_id", ""),
        "code_hash": hash_auth_code(settings.session_secret, payload.staff_user_id, code),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=settings.auth_code_ttl_seconds)).isoformat(),
        "used_at": "",
        "delivery_channel": "manual",
    }
    sheet.append_row("auth_codes", row, unique_key="auth_code_id")
    sheet.write_audit(
        action="request_login_code",
        entity="auth",
        entity_id=payload.staff_user_id,
        diff_json={"delivery_channel": "manual", "auth_code_id": auth_code_id},
        actor=payload.staff_user_id,
    )
    return LoginCodeResponse(
        delivery_channel="manual",
        expires_in_seconds=settings.auth_code_ttl_seconds,
        debug_code=code if settings.debug_auth_codes_in_response else None,
    )


@router.post("/verify-code", response_model=SessionResponse)
def verify_login_code(
    payload: LoginVerifyRequest,
    response: Response,
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    users = sheet.find("staff_users", {"staff_user_id": payload.staff_user_id})
    user = next((u for u in users if str(u.get("is_active", "")).lower() in {"1", "true", "yes"}), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    code_digits = "".join(ch for ch in payload.code if ch.isdigit())
    if len(code_digits) != 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code must be 6 digits")

    expected_hash = hash_auth_code(settings.session_secret, payload.staff_user_id, code_digits)
    matching_row = None
    for row in reversed(sheet.read_tab("auth_codes")):
        if row.get("staff_user_id") != payload.staff_user_id:
            continue
        if row.get("used_at"):
            continue
        expires_at = parse_utc_instant(str(row.get("expires_at", "")))
        if expires_at is not None and expires_at <= now:
            continue
        if row.get("code_hash") == expected_hash:
            matching_row = row
            break

    if matching_row is None:
        sheet.write_audit(
            action="verify_login_code_failed",
            entity="auth",
            entity_id=payload.staff_user_id,
            diff_json={"reason": "invalid_or_expired_code"},
            actor=payload.staff_user_id,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired code")

    sheet.update_by_id(
        "auth_codes",
        "auth_code_id",
        matching_row["auth_code_id"],
        {"used_at": now_iso},
        actor=payload.staff_user_id,
        audit_entity="auth_code",
    )

    boat_id = get_pilot_boat_id(sheet, staff_user_id=user["staff_user_id"], club_id=user.get("club_id", ""))
    token = sign_session_token(settings, _session_payload(user, boat_id=boat_id))
    _set_session_cookie(response, settings=settings, token=token)
    sheet.write_audit(
        action="login_success",
        entity="auth",
        entity_id=payload.staff_user_id,
        diff_json={"boat_id": boat_id or ""},
        actor=payload.staff_user_id,
    )
    return _session_response(user, boat_id=boat_id)


@router.get("/me", response_model=SessionResponse)
def me(
    user: AuthUser = Depends(get_current_user),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> SessionResponse:
    boat_id = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id)
    return SessionResponse(
        staff_user_id=user.staff_user_id,
        role=user.role,
        full_name=user.full_name,
        club_id=user.club_id,
        phone=user.phone,
        boat_id=boat_id,
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

    users = sheet.find("staff_users", {"staff_user_id": payload.staff_user_id})
    user = next((u for u in users if str(u.get("is_active", "")).lower() in {"1", "true", "yes"}), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    boat_id = get_pilot_boat_id(sheet, staff_user_id=user["staff_user_id"], club_id=user.get("club_id", ""))
    token = sign_session_token(settings, _session_payload(user, boat_id=boat_id))
    _set_session_cookie(response, settings=settings, token=token)
    return _session_response(user, boat_id=boat_id)




