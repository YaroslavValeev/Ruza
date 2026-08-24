from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


_REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()

DEFAULT_LAN_CORS_REGEX = r"^https?://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$"


@dataclass(frozen=True)
class Settings:
    spreadsheet_id: str
    intake_spreadsheet_id: str | None
    intake_tab_name: str
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
    agents_secret: str | None
    agents_staff_user_id: str
    telegram_bot_token: str | None
    telegram_owner_chat_id: str | None
    otp_delivery_webhook_url: str | None
    otp_delivery_webhook_token: str | None
    otp_delivery_timeout_seconds: float
    allow_manual_otp_delivery: bool
    public_club_id: str


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

    environment = os.getenv("APP_ENV", "local").strip() or "local"
    debug_auth_codes_in_response = _truthy_env("AUTH_DEBUG_CODE_IN_RESPONSE", "false")
    allow_legacy_staff_login = _truthy_env("ALLOW_LEGACY_STAFF_LOGIN", "false")
    if environment == "production" and debug_auth_codes_in_response:
        raise RuntimeError("AUTH_DEBUG_CODE_IN_RESPONSE cannot be true when APP_ENV=production")
    if environment == "production" and allow_legacy_staff_login:
        raise RuntimeError("ALLOW_LEGACY_STAFF_LOGIN cannot be true when APP_ENV=production")
    session_cookie_secure = _truthy_env("SESSION_COOKIE_SECURE", "false")
    if environment == "production" and not session_cookie_secure:
        raise RuntimeError("SESSION_COOKIE_SECURE must be true when APP_ENV=production")

    otp_delivery_webhook_url = os.getenv("OTP_DELIVERY_WEBHOOK_URL", "").strip() or None
    otp_delivery_webhook_token = os.getenv("OTP_DELIVERY_WEBHOOK_TOKEN", "").strip() or None
    allow_manual_otp_delivery = _truthy_env(
        "ALLOW_MANUAL_OTP_DELIVERY",
        "false" if environment == "production" else "true",
    )
    if environment == "production":
        if allow_manual_otp_delivery:
            raise RuntimeError("ALLOW_MANUAL_OTP_DELIVERY cannot be true when APP_ENV=production")
        if not otp_delivery_webhook_url:
            raise RuntimeError("OTP_DELIVERY_WEBHOOK_URL is required when APP_ENV=production")
        if not otp_delivery_webhook_url.lower().startswith("https://"):
            raise RuntimeError("OTP_DELIVERY_WEBHOOK_URL must use HTTPS when APP_ENV=production")
        if not otp_delivery_webhook_token:
            raise RuntimeError("OTP_DELIVERY_WEBHOOK_TOKEN is required when APP_ENV=production")

    return Settings(
        spreadsheet_id=spreadsheet_id,
        intake_spreadsheet_id=os.getenv("INTAKE_SPREADSHEET_ID", "").strip() or None,
        intake_tab_name=os.getenv("INTAKE_TAB_NAME", "Ruza").strip() or "Ruza",
        service_account_json_path=service_account_json_path,
        service_account_info=service_account_info,
        session_secret=session_secret,
        session_max_age_seconds=int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800")),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "icebeach_session"),
        session_cookie_secure=session_cookie_secure,
        allow_legacy_staff_login=allow_legacy_staff_login,
        auth_code_ttl_seconds=int(os.getenv("AUTH_CODE_TTL_SECONDS", "300")),
        auth_code_rate_limit_window_seconds=int(os.getenv("AUTH_CODE_RATE_LIMIT_WINDOW_SECONDS", "600")),
        auth_code_rate_limit_max_attempts=int(os.getenv("AUTH_CODE_RATE_LIMIT_MAX_ATTEMPTS", "5")),
        debug_auth_codes_in_response=debug_auth_codes_in_response,
        cors_allow_origins=cors_allow_origins,
        cors_allow_origin_regex=cors_allow_origin_regex,
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        environment=environment,
        agents_secret=os.getenv("AGENTS_SECRET", "").strip() or None,
        agents_staff_user_id=os.getenv("AGENTS_STAFF_USER_ID", "system-agent").strip() or "system-agent",
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None,
        telegram_owner_chat_id=os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip() or None,
        otp_delivery_webhook_url=otp_delivery_webhook_url,
        otp_delivery_webhook_token=otp_delivery_webhook_token,
        otp_delivery_timeout_seconds=float(os.getenv("OTP_DELIVERY_TIMEOUT_SECONDS", "8")),
        allow_manual_otp_delivery=allow_manual_otp_delivery,
        public_club_id=os.getenv("PUBLIC_CLUB_ID", "ice_beach_ruza").strip() or "ice_beach_ruza",
    )
