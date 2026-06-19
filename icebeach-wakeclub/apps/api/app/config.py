from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

DEFAULT_LAN_CORS_REGEX = r"^https?://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$"


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str
    service_account_json_path: str | None
    service_account_info: dict[str, Any] | None
    session_secret: str
    session_max_age_seconds: int
    session_cookie_name: str
    session_cookie_secure: bool
    allow_legacy_staff_login: bool
    auth_code_ttl_seconds: int
    auth_code_rate_limit_window_seconds: int
    auth_code_rate_limit_max_attempts: int
    debug_auth_codes_in_response: bool
    cors_allow_origins: tuple[str, ...]
    cors_allow_origin_regex: str | None
    api_host: str
    api_port: int
    environment: str


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}


def _parse_csv(value: str) -> tuple[str, ...]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    return tuple(items)


def _load_service_account_info() -> dict[str, Any] | None:
    inline_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_INLINE", "").strip()
    if inline_json:
        return json.loads(inline_json)

    base64_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", "").strip()
    if base64_json:
        decoded = base64.b64decode(base64_json).decode("utf-8")
        return json.loads(decoded)

    return None


def get_settings() -> Settings:
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "").strip()
    service_account_json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or None
    service_account_info = _load_service_account_info()
    session_secret = os.getenv("SESSION_SECRET", "").strip()

    if not spreadsheet_id:
        raise RuntimeError("SPREADSHEET_ID is required")
    if not service_account_json_path and service_account_info is None:
        raise RuntimeError(
            "One of GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SERVICE_ACCOUNT_JSON_INLINE or GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 is required"
        )
    if service_account_json_path and not Path(service_account_json_path).exists() and service_account_info is None:
        raise RuntimeError(f"Service account JSON not found: {service_account_json_path}")
    if not session_secret:
        raise RuntimeError("SESSION_SECRET is required")

    cors_allow_origins = _parse_csv(
        os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )
    cors_allow_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", DEFAULT_LAN_CORS_REGEX).strip() or None

    return Settings(
        spreadsheet_id=spreadsheet_id,
        service_account_json_path=service_account_json_path,
        service_account_info=service_account_info,
        session_secret=session_secret,
        session_max_age_seconds=int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800")),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "icebeach_session"),
        session_cookie_secure=_truthy_env("SESSION_COOKIE_SECURE", "false"),
        allow_legacy_staff_login=_truthy_env("ALLOW_LEGACY_STAFF_LOGIN", "false"),
        auth_code_ttl_seconds=int(os.getenv("AUTH_CODE_TTL_SECONDS", "300")),
        auth_code_rate_limit_window_seconds=int(os.getenv("AUTH_CODE_RATE_LIMIT_WINDOW_SECONDS", "600")),
        auth_code_rate_limit_max_attempts=int(os.getenv("AUTH_CODE_RATE_LIMIT_MAX_ATTEMPTS", "5")),
        debug_auth_codes_in_response=_truthy_env("AUTH_DEBUG_CODE_IN_RESPONSE", "false"),
        cors_allow_origins=cors_allow_origins,
        cors_allow_origin_regex=cors_allow_origin_regex,
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        environment=os.getenv("APP_ENV", "local").strip() or "local",
    )
