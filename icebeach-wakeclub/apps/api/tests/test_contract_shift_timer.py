from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from threading import Barrier
from time import sleep

CLUB_TZ = ZoneInfo("Europe/Moscow")

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.bookings import update_booking_status
from apps.api.app.services import shift_timer
from apps.api.app.services.shift_timer import get_shift_live, process_shift_reminders, run_timer_action, update_booking_prep

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
    update_booking_status(
        sheet,
        booking_id="bkg_timer_flow",
        status_value="ready",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
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
    update_booking_status(
        sheet,
        booking_id="bkg_current",
        status_value="ready",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
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


def test_shift_reminders_follow_t15_then_t5_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.api.app.services.notifications._send_telegram_message", lambda **kwargs: None)
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
    settings = replace(make_test_settings(), telegram_bot_token="test-bot", telegram_owner_chat_id="test-owner")
    sheet.tabs["clients"][0]["telegram_id"] = "test-client"

    t15 = process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 45, tzinfo=CLUB_TZ),
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
        now=datetime(2026, 6, 1, 9, 46, tzinfo=CLUB_TZ),
    )
    assert item["status"] == "late"
    row = next(entry for entry in sheet.read_tab("bookings") if entry["booking_id"] == "bkg_reminder")
    assert row["client_notice_15_sent_at"]

    t5 = process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 55, tzinfo=CLUB_TZ),
    )
    assert t5["admin_notices_sent"] == 1
    assert t5["client_notices_sent"] == 1
    row = next(entry for entry in sheet.read_tab("bookings") if entry["booking_id"] == "bkg_reminder")
    assert row["client_notice_5_sent_at"]
    app.dependency_overrides.clear()


def test_warmup_does_not_set_ready_without_explicit_handoff() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)
    created = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_handoff",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert created.status_code == 200
    settings = make_test_settings()
    item = update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_handoff",
        arrival_action="arrived",
        warmup_state="warmed_up",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 50, tzinfo=timezone.utc),
    )
    assert item["status"] == "arrived"
    assert item["warmup_state"] == "warmed_up"
    handed_off = update_booking_status(
        sheet,
        booking_id="bkg_handoff",
        status_value="ready",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
    )
    assert handed_off["status"] == "ready"
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
        now=datetime(2026, 6, 1, 9, 45, tzinfo=CLUB_TZ),
    )
    update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_reminder_arrived",
        arrival_action="late",
        warmup_state=None,
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 46, tzinfo=CLUB_TZ),
    )
    update_booking_prep(
        sheet,
        settings,
        booking_id="bkg_reminder_arrived",
        arrival_action="arrived",
        warmup_state=None,
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 9, 53, tzinfo=CLUB_TZ),
    )
    t5 = process_shift_reminders(
        sheet,
        settings,
        club_id="ice_beach_ruza",
        actor_staff_user_id="system-agent",
        now=datetime(2026, 6, 1, 9, 55, tzinfo=CLUB_TZ),
    )
    assert t5["client_notices_sent"] == 0
    app.dependency_overrides.clear()


def test_shift_live_prefers_on_water_else_next_actionable_client() -> None:
    sheet = MockSheetWrapper()
    settings = make_test_settings()
    sheet.tabs["bookings"].append(
        {
            "booking_id": "bkg_seed_ready",
            "club_id": "ice_beach_ruza",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "status": "ready",
            "total_price": "12000",
            "created_by": "staff_001",
            "created_at": "2026-06-01T07:00:00Z",
            "updated_at": "2026-06-01T07:00:00Z",
            "coach_required": "false",
            "coach_user_id": "",
            "ride_type": "wakeboard",
            "sets_count": "1",
            "wetsuit_required": "false",
            "wetsuit_size": "",
            "wetsuit_gender": "",
            "warmup_state": "pending",
            "timer_state": "idle",
            "timer_started_at": "",
            "timer_anchor_at": "",
            "elapsed_seconds": "0",
            "actual_duration_seconds": "0",
            "admin_notice_15_sent_at": "",
            "admin_notice_5_sent_at": "",
            "client_notice_15_sent_at": "",
            "client_notice_5_sent_at": "",
            "next_client_notified_at": "",
            "notes": "",
        }
    )
    sheet.tabs["bookings"].append(
        {
            "booking_id": "bkg_current_arrived",
            "club_id": "ice_beach_ruza",
            "client_id": "client_2",
            "date": "2026-06-01",
            "time": "15:00",
            "boat_id": "boat_1",
            "status": "arrived",
            "total_price": "12000",
            "created_by": "staff_001",
            "created_at": "2026-06-01T14:00:00Z",
            "updated_at": "2026-06-01T14:30:00Z",
            "coach_required": "false",
            "coach_user_id": "",
            "ride_type": "wakeboard",
            "sets_count": "1",
            "wetsuit_required": "false",
            "wetsuit_size": "",
            "wetsuit_gender": "",
            "warmup_state": "warmed_up",
            "timer_state": "idle",
            "timer_started_at": "",
            "timer_anchor_at": "",
            "elapsed_seconds": "0",
            "actual_duration_seconds": "0",
            "admin_notice_15_sent_at": "",
            "admin_notice_5_sent_at": "",
            "client_notice_15_sent_at": "",
            "client_notice_5_sent_at": "",
            "next_client_notified_at": "",
            "notes": "",
        }
    )

    operator_focus = get_shift_live(sheet, club_id="ice_beach_ruza", target_date="2026-06-01", role="operator")
    assert operator_focus["focus_booking"]["booking_id"] == "bkg_current_arrived"

    update_booking_status(
        sheet,
        booking_id="bkg_current_arrived",
        status_value="ready",
        actor_staff_user_id="staff_001",
        club_id="ice_beach_ruza",
    )
    run_timer_action(
        sheet,
        settings,
        booking_id="bkg_current_arrived",
        action="start",
        actor_staff_user_id="staff_pilot",
        club_id="ice_beach_ruza",
        now=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
    )
    live_focus = get_shift_live(sheet, club_id="ice_beach_ruza", target_date="2026-06-01", role="operator")
    assert live_focus["focus_booking"]["booking_id"] == "bkg_current_arrived"


def _service_booking(booking_id: str, *, status: str = "ready", time: str = "10:00") -> dict[str, str]:
    return {
        "booking_id": booking_id,
        "club_id": "ice_beach_ruza",
        "client_id": "client_1",
        "date": "2026-06-01",
        "time": time,
        "boat_id": "boat_1",
        "status": status,
        "sets_count": "1",
        "warmup_state": "pending",
        "timer_state": "idle",
    }


@pytest.mark.parametrize("status", ["confirmed", "late"])
@pytest.mark.parametrize("warmup_state", ["pending", "warmed_up", "no_warmup"])
def test_combined_late_and_warmup_is_rejected_before_any_side_effect(status: str, warmup_state: str) -> None:
    sheet = MockSheetWrapper()
    sheet.tabs["bookings"].append(_service_booking("prep-atomic", status=status))
    before = deepcopy(sheet.tabs)
    with pytest.raises(HTTPException) as exc_info:
        update_booking_prep(
            sheet, make_test_settings(), booking_id="prep-atomic", arrival_action="late",
            warmup_state=warmup_state, actor_staff_user_id="staff_001", club_id="ice_beach_ruza",
            now=datetime(2026, 6, 1, 9, 45, tzinfo=CLUB_TZ),
        )
    assert exc_info.value.status_code == 409
    assert sheet.tabs == before


def test_combined_arrival_and_warmup_remains_supported() -> None:
    sheet = MockSheetWrapper()
    sheet.tabs["bookings"].append(_service_booking("prep-arrival", status="confirmed"))
    item = update_booking_prep(
        sheet, make_test_settings(), booking_id="prep-arrival", arrival_action="arrived",
        warmup_state="warmed_up", actor_staff_user_id="staff_001", club_id="ice_beach_ruza",
    )
    assert item["status"] == "arrived" and item["warmup_state"] == "warmed_up"


@pytest.mark.parametrize("timer_state", ["running", "paused"])
def test_start_rejects_another_active_ride_on_same_club_boat(timer_state: str) -> None:
    sheet = MockSheetWrapper()
    active = _service_booking("active-ride", status="in_progress")
    active["timer_state"] = timer_state
    sheet.tabs["bookings"].extend([active, _service_booking("next-ride", time="11:00")])
    before = deepcopy(sheet.tabs)
    with pytest.raises(HTTPException) as exc_info:
        run_timer_action(
            sheet, make_test_settings(), booking_id="next-ride", action="start",
            actor_staff_user_id="staff_pilot", club_id="ice_beach_ruza",
        )
    assert exc_info.value.status_code == 409
    assert sheet.tabs == before


@pytest.mark.parametrize("separate_scope", [{"boat_id": "boat_2"}, {"club_id": "other-club"}])
def test_start_does_not_block_another_boat_or_club(separate_scope: dict[str, str]) -> None:
    sheet = MockSheetWrapper()
    active = {**_service_booking("active-ride", status="in_progress"), **separate_scope}
    sheet.tabs["bookings"].extend([active, _service_booking("next-ride", time="11:00")])
    item = run_timer_action(
        sheet, make_test_settings(), booking_id="next-ride", action="start",
        actor_staff_user_id="staff_pilot", club_id="ice_beach_ruza",
    )
    assert item["status"] == "in_progress" and item["timer_state"] == "running"


@pytest.mark.parametrize("coach_user_id,expected_booking_id", [("staff_coach", "assigned-ride"), ("other-coach", None)])
def test_coach_live_focus_only_selects_assigned_session(coach_user_id: str, expected_booking_id: str | None) -> None:
    sheet = MockSheetWrapper()
    unassigned = _service_booking("unassigned-ride", status="in_progress")
    assigned = {
        **_service_booking("assigned-ride", time="11:00"),
        "coach_required": "true", "coach_user_id": "staff_coach",
    }
    sheet.tabs["bookings"].extend([unassigned, assigned])
    before = deepcopy(sheet.tabs)
    focus = get_shift_live(
        sheet, club_id="ice_beach_ruza", target_date="2026-06-01", role="coach", coach_user_id=coach_user_id,
    )["focus_booking"]
    assert (focus["booking_id"] if focus is not None else None) == expected_booking_id
    assert sheet.tabs == before


@pytest.mark.parametrize("same_booking", [False, True])
def test_direct_concurrent_start_serializes_one_active_ride(same_booking: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    sheet = MockSheetWrapper()
    sheet.tabs["bookings"].extend([_service_booking("first-ride"), _service_booking("next-ride", time="11:00")])
    original_get_row = shift_timer.get_booking_row

    def slow_get_row(*args, **kwargs):
        row = original_get_row(*args, **kwargs)
        sleep(0.01)
        return row

    monkeypatch.setattr(shift_timer, "get_booking_row", slow_get_row)
    barrier = Barrier(2)

    def start(booking_id: str) -> int:
        barrier.wait(timeout=5)
        try:
            run_timer_action(
                sheet, make_test_settings(), booking_id=booking_id, action="start",
                actor_staff_user_id="staff_pilot", club_id="ice_beach_ruza",
            )
        except HTTPException as exc:
            return exc.status_code
        return 200

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(start, "first-ride"), executor.submit(start, "first-ride" if same_booking else "next-ride")]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(results) == [200, 409]
    assert len([row for row in sheet.tabs["bookings"] if row["status"] == "in_progress"]) == 1
