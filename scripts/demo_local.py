#!/usr/bin/env python3
"""Local demo API with in-memory Sheets. No Google credentials required.

[WSL2]
PYTHONPATH=/workspace/icebeach-wakeclub python3 scripts/demo_local.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "icebeach-wakeclub"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

os.environ.setdefault("SPREADSHEET_ID", "demo-sheet")
os.environ.setdefault("SESSION_SECRET", "demo-secret-not-for-production")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON", str(Path(__file__).resolve()))
os.environ.setdefault("AUTH_DEBUG_CODE_IN_RESPONSE", "true")
os.environ.setdefault("APP_ENV", "demo")

from apps.api.app.config import Settings, get_settings  # noqa: E402
from apps.api.app.dependencies import get_sheet_wrapper  # noqa: E402
from apps.api.app.main import create_app  # noqa: E402
from packages.sheets.memory import InMemorySheetWrapper, demo_tabs  # noqa: E402


def build_demo_app():
    store = InMemorySheetWrapper(demo_tabs())
    settings = Settings(
        spreadsheet_id="demo-sheet",
        service_account_json_path=str(Path(__file__).resolve()),
        service_account_info=None,
        session_secret="demo-secret-not-for-production",
        session_max_age_seconds=28800,
        session_cookie_name="icebeach_session",
        session_cookie_secure=False,
        allow_legacy_staff_login=False,
        auth_code_ttl_seconds=300,
        auth_code_rate_limit_window_seconds=600,
        auth_code_rate_limit_max_attempts=20,
        debug_auth_codes_in_response=True,
        cors_allow_origins=("http://127.0.0.1:5173", "http://localhost:5173"),
        cors_allow_origin_regex=None,
        api_host="127.0.0.1",
        api_port=8000,
        environment="demo",
    )
    application = create_app(settings)
    application.dependency_overrides[get_sheet_wrapper] = lambda: store
    application.dependency_overrides[get_settings] = lambda: settings
    return application


app = build_demo_app()


if __name__ == "__main__":
    import uvicorn

    print("Demo login: phone +79990000000 (admin) / +79990000001 (operator) / +79990000002 (pilot)")
    print("OTP is shown on the login screen (AUTH_DEBUG_CODE_IN_RESPONSE=true).")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
