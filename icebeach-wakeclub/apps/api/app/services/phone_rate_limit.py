from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException, status

from ..config import Settings
from .common import normalize_phone, phone_key_last10

# Public endpoints can receive arbitrary phone numbers. Keep the in-process
# limiter bounded so a high-cardinality scan cannot retain one dictionary entry
# per submitted number for the lifetime of the worker.
_MAX_KEYS_PER_SCOPE = 10_000
_BUCKETS: dict[str, OrderedDict[str, list[datetime]]] = {}
_BUCKETS_LOCK = Lock()


def reset_phone_rate_limits() -> None:
    with _BUCKETS_LOCK:
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
    limited = False

    with _BUCKETS_LOCK:
        bucket = _BUCKETS.setdefault(scope, OrderedDict())
        recent = [stamp for stamp in bucket.get(key, []) if now - stamp <= window]

        if len(recent) >= settings.auth_code_rate_limit_max_attempts:
            limited = True
        else:
            recent.append(now)

        bucket[key] = recent
        bucket.move_to_end(key)

        while len(bucket) > _MAX_KEYS_PER_SCOPE:
            bucket.popitem(last=False)

    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests for this phone")
