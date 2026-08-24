from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from packages.sheets import SheetWrapper

from .config import Settings, get_settings
from .dependencies import get_sheet_wrapper
from .services.common import parse_bool


security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    staff_user_id: str
    role: str
    full_name: str
    club_id: str
    phone: str = ""


def make_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="icebeach-session")


def sign_session_token(settings: Settings, payload: dict[str, str]) -> str:
    return make_serializer(settings).dumps(payload)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> AuthUser:
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get(settings.session_cookie_name)

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session token")

    serializer = make_serializer(settings)
    try:
        payload = serializer.loads(token, max_age=settings.session_max_age_seconds)
    except SignatureExpired as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    required_fields = ("staff_user_id", "role", "full_name", "club_id")
    if not all(payload.get(field) for field in required_fields):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    records = sheet.find("staff_users", {"staff_user_id": payload["staff_user_id"]})
    live = next((row for row in records if parse_bool(row.get("is_active"))), None)
    if live is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return AuthUser(
        staff_user_id=live["staff_user_id"],
        role=live.get("role") or payload["role"],
        full_name=live.get("full_name") or payload["full_name"],
        club_id=live.get("club_id") or payload["club_id"],
        phone=live.get("phone") or payload.get("phone", ""),
    )


def require_roles(*allowed_roles: str) -> Callable[[AuthUser], AuthUser]:
    def dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this role")
        return user

    return dependency
