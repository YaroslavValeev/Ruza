from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import secrets


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def weekday_iso0(date_text: str) -> int:
    parsed = date.fromisoformat(date_text)
    return parsed.weekday()


def normalize_phone(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def hash_auth_code(secret: str, staff_user_id: str, code: str) -> str:
    payload = f"{secret}:{staff_user_id}:{code}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_auth_code(length: int = 6) -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def utc_now() -> datetime:
    return datetime.utcnow()

def phone_key_last10(value: str) -> str:
    digits = normalize_phone(value)
    return digits[-10:] if len(digits) >= 10 else digits


def phones_match(expected: str, provided: str) -> bool:
    # Accept "+7XXXXXXXXXX" and "8XXXXXXXXXX" and other formatting differences.
    return normalize_phone(expected) == normalize_phone(provided) or phone_key_last10(expected) == phone_key_last10(provided)


def parse_utc_instant(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
