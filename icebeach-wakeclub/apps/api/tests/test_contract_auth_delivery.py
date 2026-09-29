from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.otp_delivery import deliver_login_code
from conftest import MockSheetWrapper, make_test_settings


class _AcceptedResponse:
    def raise_for_status(self) -> None:
        return None


def test_phone_webhook_receives_staff_otp(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return _AcceptedResponse()

    monkeypatch.setattr("apps.api.app.services.otp_delivery.httpx.post", fake_post)
    settings = replace(
        make_test_settings(),
        otp_delivery_webhook_url="https://otp.example/send",
        otp_delivery_webhook_token="provider-secret",
        allow_manual_otp_delivery=False,
    )

    channel = deliver_login_code(code="123456", phone="+79990000001", settings=settings)

    assert channel == "phone_webhook"
    assert captured["url"] == "https://otp.example/send"
    assert captured["headers"] == {"Authorization": "Bearer provider-secret"}
    assert captured["json"] == {
        "phone": "+79990000001",
        "code": "123456",
        "purpose": "staff_login",
    }


def test_failed_delivery_invalidates_auth_code() -> None:
    mock_sheet = MockSheetWrapper()
    strict_settings = replace(make_test_settings(), allow_manual_otp_delivery=False)
    app.dependency_overrides[get_sheet_wrapper] = lambda: mock_sheet
    app.dependency_overrides[get_settings] = lambda: strict_settings
    client = TestClient(app)

    response = client.post(
        "/auth/request-code",
        json={"staff_user_id": "staff_001", "phone": "+79990000001"},
    )

    assert response.status_code == 503
    auth_code = mock_sheet.read_tab("auth_codes")[-1]
    assert auth_code["delivery_channel"] == "failed"
    assert auth_code["used_at"]
    app.dependency_overrides.clear()


def test_production_settings_require_https_phone_provider(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DEBUG_CODE_IN_RESPONSE", "false")
    monkeypatch.setenv("ALLOW_LEGACY_STAFF_LOGIN", "false")
    monkeypatch.setenv("ALLOW_MANUAL_OTP_DELIVERY", "false")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("SPREADSHEET_ID", "test-sheet")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(Path(__file__).resolve()))
    monkeypatch.delenv("OTP_DELIVERY_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("OTP_DELIVERY_WEBHOOK_TOKEN", raising=False)

    try:
        get_settings()
        raise AssertionError("expected RuntimeError for missing production OTP provider")
    except RuntimeError as exc:
        assert "OTP_DELIVERY_WEBHOOK_URL" in str(exc)

    monkeypatch.setenv("OTP_DELIVERY_WEBHOOK_URL", "http://otp.example/send")
    monkeypatch.setenv("OTP_DELIVERY_WEBHOOK_TOKEN", "provider-secret")
    try:
        get_settings()
        raise AssertionError("expected RuntimeError for insecure production OTP provider")
    except RuntimeError as exc:
        assert "HTTPS" in str(exc)

    monkeypatch.setenv("OTP_DELIVERY_WEBHOOK_URL", "https://otp.example/send")
    monkeypatch.setenv("INTAKE_SPREADSHEET_ID", "intake-sheet")
    monkeypatch.setenv("AGENTS_SECRET", "agents-secret")
    settings = get_settings()
    assert settings.otp_delivery_webhook_url == "https://otp.example/send"
    assert settings.allow_manual_otp_delivery is False


def test_production_settings_require_intake_and_agents_secret(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DEBUG_CODE_IN_RESPONSE", "false")
    monkeypatch.setenv("ALLOW_LEGACY_STAFF_LOGIN", "false")
    monkeypatch.setenv("ALLOW_MANUAL_OTP_DELIVERY", "false")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("SPREADSHEET_ID", "test-sheet")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(Path(__file__).resolve()))
    monkeypatch.setenv("OTP_DELIVERY_WEBHOOK_URL", "https://otp.example/send")
    monkeypatch.setenv("OTP_DELIVERY_WEBHOOK_TOKEN", "provider-secret")
    monkeypatch.delenv("INTAKE_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("AGENTS_SECRET", raising=False)

    try:
        get_settings()
        raise AssertionError("expected RuntimeError for missing production intake spreadsheet")
    except RuntimeError as exc:
        assert "INTAKE_SPREADSHEET_ID" in str(exc)

    monkeypatch.setenv("INTAKE_SPREADSHEET_ID", "intake-sheet")
    try:
        get_settings()
        raise AssertionError("expected RuntimeError for missing production agents secret")
    except RuntimeError as exc:
        assert "AGENTS_SECRET" in str(exc)

    monkeypatch.setenv("AGENTS_SECRET", "agents-secret")
    settings = get_settings()
    assert settings.intake_spreadsheet_id == "intake-sheet"
    assert settings.agents_secret == "agents-secret"
