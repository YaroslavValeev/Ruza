"""Session token helpers and RBAC checks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

SECRET = os.environ.get("API_SESSION_SECRET", "dev-insecure-secret")

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"*"},
    "operator": {"read:ops", "write:ops", "read:kpi"},
    "pilot": {"read:pilot", "write:pilot"},
    "coach": {"read:coach", "write:coach"},
    "marketing_read": {"read:kpi", "read:marketing"},
}


def _sign(payload: str) -> str:
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return signature


def create_session_token(staff_user_id: str, role: str, ttl_minutes: int = 480) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ttl_minutes)
    body = {
        "staff_user_id": staff_user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    payload = base64.urlsafe_b64encode(json.dumps(body).encode()).decode()
    return f"{payload}.{_sign(payload)}"


def parse_session_token(token: str) -> dict:
    try:
        payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    if not hmac.compare_digest(_sign(payload), signature):
        raise ValueError("Invalid token signature")

    body = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    if body["exp"] < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Session expired")
    return body


def has_permission(role: str, permission: str) -> bool:
    role_permissions = ROLE_PERMISSIONS.get(role, set())
    return "*" in role_permissions or permission in role_permissions
