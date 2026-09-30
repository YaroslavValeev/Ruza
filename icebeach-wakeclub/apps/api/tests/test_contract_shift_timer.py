from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.shift_timer import process_shift_reminders, run_timer_action, update_booking_prep

from conftest import MockSheetWrapper, make_test_settings


def _client(mock_sheet: MockSheetWrapper) -> TestClient:
    app.dependency_overrides[get_sheet_wrapper] = lambda: mock_sheet
    app.dependency_overrides[get_settings] = make_test_settings
    return TestClient(app)


def _login(client: TestClient, staff_user_id: str = "staff_001", phone: str = "+79990000001") -> None:
    request_code = client.post("/auth/request-code", json={"staff_user_id": staff_user_id, "phone": phone})
    assert request_code.status_code == 200
    verify = client.post("/auth/verify-code", json={"staff_user_id": staff_user_id, "code": request_code.json()["debug_code"]})
    assert verify.status_code == 200


def test_booking_sets_drive_duration_and_multi_slot_capacity() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)

    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_sets_3",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "sets_count": 3,
        },
    )
    assert created.status_code == 200

    availability = client.get("/availability?date=2026-06-01")
    assert availability.status_code == 200
    payload = {row["time"]: row for row in availability.json()}
    assert payload["10:00"]["booked"] == 1
    assert payload["10:30"]["booked"] == 1
    assert payload["11:00"]["booked"] == 1

    listed = client.get("/bookings?date=2026-06-01")
    item = next(row for row in listed.json() if row["booking_id"] == "bkg_sets_3")
    assert item["sets_count"] == 3
    assert item["planned_duration_minutes"] == 75

    second_client = client.post("/clients", json={"full_name": "Client Two", "phone": "+79990000077"})
    assert second_client.status_code == 200
    conflict = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_sets_conflict",
            "client_id": second_client.json()["client_id"],
            "date": "2026-06-01",
            "time": "10:30",
            "boat_id": "boat_1",
        },
    )
    assert conflict.status_code == 409
    app.dependency_overrides.clear()


def test_pilot_timer_flow_records_actual_vs_planned_minutes() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)
    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_timer_flow",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "sets_count": 2,
        },
    )
    assert created.status_code == 200

    settings = make_test_settings()
    update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_timer_flow",
        arrival_action="arrived",
        warmup_state="warmed_up",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 58, tzinfo=timezone.utc),
    )
    run_timer_action(
        sheet,
        settings,
        booking_id="bkg_timer_flow",
        action="start",
        actor_staff_user_id="staff_pilot",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
    )
    run_timer_action(
        sheet,
        settings,
        booking_id="bkg_timer_flow",
        action="pause",
        actor_staff_user_id="staff_pilot",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 10, 12, tzinfo=timezone.utc),
    )
    final_item = run_timer_action(
        sheet,
        settings,
        booking_id="bkg_timer_flow",
        action="stop",
        actor_staff_user_id="staff_pilot",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 10, 12, tzinfo=timezone.utc),
    )

    assert final_item["status"] == "done"
    assert final_item["planned_duration_minutes"] == 50
    assert final_item["actual_duration_seconds"] == 12 * 60
    assert final_item["total_price"] == 12000
    app.dependency_overrides.clear()


def test_add_set_is_blocked_when_next_slot_is_taken() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)
    first = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_current",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert first.status_code == 200
    second_client = client.post("/clients", json={"full_name": "Client Two", "phone": "+79990000088"})
    assert second_client.status_code == 200
    second = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_next_slot",
            "client_id": second_client.json()["client_id"],
            "date": "2026-06-01",
            "time": "10:30",
            "boat_id": "boat_1",
        },
    )
    assert second.status_code == 200

    settings = make_test_settings()
    update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_current",
        arrival_action="arrived",
        warmup_state="no_warmup",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 58, tzinfo=timezone.utc),
    )
    run_timer_action(
        sheet,
        settings,
        booking_id="bkg_current",
        action="start",
        actor_staff_user_id="staff_pilot",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as exc_info:
        run_timer_action(
            sheet,
            settings,
            booking_id="bkg_current",
            action="add_set",
            actor_staff_user_id="staff_pilot",
            club_id="ice_beach_ruza",
            now=datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc),
        )
    assert exc_info.value.status_code == 409
    app.dependency_overrides.clear()


def test_shift_reminders_follow_t15_then_t5_rules() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)
    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_reminder",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert created.status_code == 200
    settings = make_test_settings()

    t15 = process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 45, tzinfo=timezone.utc),
    )
    assert t15["admin_notices_sent"] == 1
    assert t15["client_notices_sent"] == 0

    item = update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_reminder",
        arrival_action="late",
        warmup_state=None,
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 46, tzinfo=timezone.utc),
    )
    assert item["status"] == "late"
    row = next(entry for entry in sheet.read_tab("bookings") if entry["booking_id"] == "bkg_reminder")
    assert row["client_notice_15_sent_at"]

    t5 = process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 55, tzinfo=timezone.utc),
    )
    assert t5["admin_notices_sent"] == 1
    assert t5["client_notices_sent"] == 1
    row = next(entry for entry in sheet.read_tab("bookings") if entry["booking_id"] == "bkg_reminder")
    assert row["client_notice_5_sent_at"]
    app.dependency_overrides.clear()


def test_second_client_notice_is_skipped_after_arrival() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)
    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_reminder_arrived",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert created.status_code == 200
    settings = make_test_settings()
    process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 45, tzinfo=timezone.utc),
    )
    update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_reminder_arrived",
        arrival_action="late",
        warmup_state=None,
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 46, tzinfo=timezone.utc),
    )
    update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_reminder_arrived",
        arrival_action="arrived",
        warmup_state=None,
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 53, tzinfo=timezone.utc),
    )
    t5 = process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 55, tzinfo=timezone.utc),
    )
    assert t5["client_notices_sent"] == 0
    app.dependency_overrides.clear()
