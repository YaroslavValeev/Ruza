from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from ..config import Settings
from .common import normalize_phone, phone_key_last10

_BUCKETS: dict[str, dict[str, list[datetime]]] = {}


def reset_phone_rate_limits() -> None:
    _BUCKETS.clear()


def enforce_phone_rate_limit(phone: str, settings: Settings, *, scope: str) -> None:
    """Count attempts by phone before a staff record is required.

    Unknown numbers are limited the same way as known ones. Login still returns
    a distinct not-found response so the existing phone login flow can show a name.
    """
    key = phone_key_last10(phone) or normalize_phone(phone)
    if not key:
        return
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=settings.auth_code_rate_limit_window_seconds)
    bucket = _BUCKETS.setdefault(scope, {})
    recent = [stamp for stamp in bucket.get(key, []) if now - stamp <= window]
    if len(recent) >= settings.auth_code_rate_limit_max_attempts:
        bucket[key] = recent
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests for this phone")
    recent.append(now)
    bucket[key] = recent
