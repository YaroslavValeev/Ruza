from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.preflight import run_preflight_check
from apps.api.app.services.smoke import run_smoke_check
from packages.sheets.memory import InMemorySheetWrapper, demo_tabs

from conftest import MockSheetWrapper, make_test_settings


def _make_client(mock_sheet: MockSheetWrapper) -> TestClient:
    app.dependency_overrides[get_sheet_wrapper] = lambda: mock_sheet
    app.dependency_overrides[get_settings] = make_test_settings
    return TestClient(app)


def _login(client: TestClient, staff_user_id: str = "staff_001", phone: str = "+79990000001") -> None:
    request_code = client.post("/auth/request-code", json={"staff_user_id": staff_user_id, "phone": phone})
    assert request_code.status_code == 200
    code = request_code.json()["debug_code"]
    verify = client.post("/auth/verify-code", json={"staff_user_id": staff_user_id, "code": code})
    assert verify.status_code == 200


def test_shift_cycle_booking_to_kpi() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_shift_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert created.status_code == 200

    arrived = client.post(
        "/checkins",
        json={"method": "phone", "phone": "+79990000011", "date": "2026-06-01", "status": "arrived", "booking_id": "bkg_shift_1"},
    )
    assert arrived.status_code == 200
    ready = client.post(
        "/checkins",
        json={"method": "phone", "phone": "+79990000011", "date": "2026-06-01", "status": "ready", "booking_id": "bkg_shift_1"},
    )
    assert ready.status_code == 200

    pilot = _make_client(mock_sheet)
    _login(pilot, staff_user_id="staff_pilot", phone="+79990000002")
    queue = pilot.get("/pilot/today?date=2026-06-01").json()
    assert queue[0]["status"] == "ready"
    assert pilot.patch("/bookings/bkg_shift_1/status", json={"status": "in_progress"}).status_code == 200
    assert pilot.patch("/bookings/bkg_shift_1/status", json={"status": "done"}).status_code == 200
    forbidden_cancel = pilot.patch("/bookings/bkg_shift_1/status", json={"status": "cancelled"})
    assert forbidden_cancel.status_code in {403, 409}

    admin = _make_client(mock_sheet)
    _login(admin, staff_user_id="staff_admin", phone="+79990000000")
    kpi = admin.get("/kpi/summary?period=day&date_from=2026-06-01").json()
    assert kpi["sessions_count"] == 1
    assert kpi["revenue_estimate"] == 12000
    app.dependency_overrides.clear()


def test_inactive_staff_loses_session() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)
    assert client.get("/auth/me").status_code == 200
    mock_sheet.tabs["staff_users"][0]["is_active"] = "false"
    assert client.get("/auth/me").status_code == 401
    app.dependency_overrides.clear()


def test_face_checkin_requires_consent() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)
    client.post(
        "/bookings",
        json={
            "booking_id": "bkg_face_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    denied = client.post(
        "/checkins",
        json={"method": "face", "client_id": "client_1", "date": "2026-06-01", "status": "arrived"},
    )
    assert denied.status_code == 403
    app.dependency_overrides.clear()


def test_preflight_and_smoke_on_memory_store() -> None:
    mock_sheet = MockSheetWrapper(demo_tabs(today=date(2026, 6, 1)))
    summary = run_preflight_check(mock_sheet, target_date="2026-06-01")
    assert summary["blockers"] == 0
    smoke = run_smoke_check(
        mock_sheet,
        target_date="2026-06-01",
        club_id="ice_beach_ruza",
        actor_staff_user_id="staff_admin",
    )
    assert smoke["ok"] is True
    client = _make_client(mock_sheet)
    _login(client, staff_user_id="staff_admin", phone="+79990000000")
    api_smoke = client.post("/smoke/run?date=2026-06-01")
    assert api_smoke.status_code == 200
    assert api_smoke.json()["ok"] is True
    app.dependency_overrides.clear()


def test_preflight_blocks_when_leads_tab_is_missing() -> None:
    tabs = demo_tabs(today=date(2026, 6, 1))
    tabs.pop("leads")
    mock_sheet = MockSheetWrapper(tabs)

    summary = run_preflight_check(mock_sheet, target_date="2026-06-01")

    assert summary["blockers"] == 1
    assert any(item["code"] == "tab:leads" and item["level"] == "BLOCKER" for item in summary["checks"])


def test_analytics_snapshot_is_club_scoped() -> None:
    mock_sheet = MockSheetWrapper()
    mock_sheet.tabs["analytics_daily"] = [
        {
            "date": "2026-06-01",
            "club_id": "other_club",
            "sessions_count": "9",
            "utilization_pct": "10",
            "revenue_estimate": "1",
            "no_show_rate": "0",
            "notes": "other",
        }
    ]
    from apps.api.app.services.analytics_snapshot import write_analytics_snapshot

    first = write_analytics_snapshot(mock_sheet, club_id="ice_beach_ruza", target_date="2026-06-01")
    second = write_analytics_snapshot(mock_sheet, club_id="ice_beach_ruza", target_date="2026-06-01")
    assert first["written"] is True
    assert second["written"] is True
    rows = mock_sheet.read_tab("analytics_daily")
    assert len(rows) == 2
    assert {row["club_id"] for row in rows} == {"other_club", "ice_beach_ruza"}
    app.dependency_overrides.clear()


def test_marketing_read_cannot_write_utm() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client, staff_user_id="staff_marketing", phone="+79990000004")
    denied = client.post("/utm-events", json={"event_type": "page_view", "utm_source": "ig"})
    assert denied.status_code == 403
    app.dependency_overrides.clear()


def test_voice_fsm_happy_path() -> None:
    from apps.edge.voice.fsm import VoiceFsm, VoiceState

    fsm = VoiceFsm()
    state, _ = fsm.transition("")
    assert state == VoiceState.ASK_PHONE
    state, _ = fsm.transition("79990000011")
    assert state == VoiceState.CONFIRM_BOOKING
    state, reply = fsm.transition("да")
    assert state == VoiceState.DONE
    assert "подтверждён" in reply.lower() or "подтвержден" in reply.lower()


def test_operator_cannot_cancel_in_progress() -> None:
    mock_sheet = MockSheetWrapper()
    operator = _make_client(mock_sheet)
    _login(operator)
    created = operator.post(
        "/bookings",
        json={
            "booking_id": "bkg_live_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert created.status_code == 200
    assert operator.post(
        "/checkins",
        json={"method": "phone", "phone": "+79990000011", "date": "2026-06-01", "status": "arrived", "booking_id": "bkg_live_1"},
    ).status_code == 200
    assert operator.post(
        "/checkins",
        json={"method": "phone", "phone": "+79990000011", "date": "2026-06-01", "status": "ready", "booking_id": "bkg_live_1"},
    ).status_code == 200

    pilot = _make_client(mock_sheet)
    _login(pilot, staff_user_id="staff_pilot", phone="+79990000002")
    assert pilot.patch("/bookings/bkg_live_1/status", json={"status": "in_progress"}).status_code == 200

    denied = operator.patch("/bookings/bkg_live_1/status", json={"status": "cancelled"})
    assert denied.status_code == 409
    listed = operator.get("/bookings?date=2026-06-01").json()
    assert listed[0]["status"] == "in_progress"
    app.dependency_overrides.clear()


def test_face_checkin_allowed_with_consent() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)
    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_face_ok",
            "client_id": "client_2",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert created.status_code == 200
    allowed = client.post(
        "/checkins",
        json={"method": "face", "client_id": "client_2", "date": "2026-06-01", "status": "arrived"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "arrived"
    app.dependency_overrides.clear()


def test_operator_can_create_and_update_lead() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)
    created = client.post(
        "/leads",
        json={"full_name": "Новый лид", "phone": "+79990000033", "source": "offline"},
    )
    assert created.status_code == 200
    lead_id = created.json()["lead_id"]
    patched = client.patch(f"/leads/{lead_id}/status", json={"status": "contacted"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "contacted"
    app.dependency_overrides.clear()


def test_marketing_read_cannot_create_lead() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client, staff_user_id="staff_marketing", phone="+79990000004")
    denied = client.post("/leads", json={"full_name": "Лид", "phone": "+79990000044"})
    assert denied.status_code == 403
    app.dependency_overrides.clear()


def test_login_code_delivery_is_manual_without_telegram() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    response = client.post("/auth/request-code", json={"staff_user_id": "staff_001", "phone": "+79990000001"})
    assert response.status_code == 200
    assert response.json()["delivery_channel"] == "manual"
    app.dependency_overrides.clear()


def test_production_settings_reject_debug_otp(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DEBUG_CODE_IN_RESPONSE", "true")
    monkeypatch.setenv("ALLOW_LEGACY_STAFF_LOGIN", "false")
    monkeypatch.setenv("SPREADSHEET_ID", "test-sheet")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(Path(__file__).resolve()))
    try:
        get_settings()
        raise AssertionError("expected RuntimeError for debug OTP in production")
    except RuntimeError as exc:
        assert "AUTH_DEBUG_CODE_IN_RESPONSE" in str(exc)
