from __future__ import annotations

import os
import sys
from pathlib import Path

from packages.sheets.memory import InMemorySheetWrapper
from apps.api.app.config import Settings


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# CI/collection must not require live Google credentials.
os.environ.setdefault("SPREADSHEET_ID", "test-sheet")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON", str(Path(__file__).resolve()))
os.environ.setdefault("AUTH_DEBUG_CODE_IN_RESPONSE", "true")
os.environ["TELEGRAM_BOT_TOKEN"] = ""


MockSheetWrapper = InMemorySheetWrapper


def make_test_settings() -> Settings:
    return Settings(
        spreadsheet_id="test-sheet",
        intake_spreadsheet_id="test-intake-sheet",
        intake_tab_name="Ruza",
        service_account_json_path=str(Path(__file__).resolve()),
        service_account_info=None,
        session_secret="test-secret",
        session_max_age_seconds=3600,
        session_cookie_name="icebeach_session",
        session_cookie_secure=False,
        allow_legacy_staff_login=False,
        auth_code_ttl_seconds=300,
        auth_code_rate_limit_window_seconds=600,
        auth_code_rate_limit_max_attempts=5,
        debug_auth_codes_in_response=True,
        cors_allow_origins=("http://127.0.0.1:5173", "http://localhost:5173"),
        cors_allow_origin_regex=None,
        api_host="127.0.0.1",
        api_port=8000,
        environment="test",
        agents_secret="test-agents-secret",
        agents_staff_user_id="system-agent",
        telegram_bot_token=None,
        telegram_owner_chat_id=None,
        otp_delivery_webhook_url=None,
        otp_delivery_webhook_token=None,
        otp_delivery_timeout_seconds=8.0,
        allow_manual_otp_delivery=True,
        public_club_id="ice_beach_ruza",
    )
