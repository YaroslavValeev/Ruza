"""Cross-role operator scenarios; no live Sheets, messages, or network calls."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_intake_sheet_wrapper, get_sheet_wrapper
from apps.api.app.main import create_app
from packages.sheets import SheetWrapper

from conftest import MockSheetWrapper, make_test_settings


DAY = "2026-06-01"
CLUB = "ice_beach_ruza"
STAFF = {
    "admin": ("staff_admin", "+79990000000"),
    "operator": ("staff_001", "+79990000001"),
    "pilot": ("staff_pilot", "+79990000002"),
    "coach": ("staff_coach", "+79990000003"),
    "marketing_read": ("staff_marketing", "+79990000004"),
}


class Scenario:
    def __init__(self):
        self.sheet = MockSheetWrapper()
        self.source = MockSheetWrapper({"Ruza": []})
        self.settings = make_test_settings()
        self.app = create_app(self.settings)
        self.app.dependency_overrides[get_sheet_wrapper] = lambda: self.sheet
        self.app.dependency_overrides[get_intake_sheet_wrapper] = lambda: self.source
        self.app.dependency_overrides[get_settings] = lambda: self.settings
        self.clients = {}
        self.now = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)

    def client(self, role):
        if role not in self.clients:
            client = TestClient(self.app, raise_server_exceptions=False)
            staff_id, phone = STAFF[role]
            requested = client.post("/auth/request-code", json={"staff_user_id": staff_id, "phone": phone})
            assert requested.status_code == 200, requested.text
            verified = client.post(
                "/auth/verify-code",
                json={"staff_user_id": staff_id, "code": requested.json()["debug_code"]},
            )
            assert verified.status_code == 200, verified.text
            self.clients[role] = client
        return self.clients[role]

    def booking(self, booking_id="scenario-ride", **overrides):
        payload = {
            "booking_id": booking_id,
            "client_id": "client_1",
            "date": DAY,
            "time": "10:00",
            "boat_id": "boat_1",
            **overrides,
        }
        response = self.client("operator").post("/bookings", json=payload)
        assert response.status_code == 200, response.text
        return payload

    def ready(self, booking_id="scenario-ride"):
        operator = self.client("operator")
        arrived = operator.patch(f"/bookings/{booking_id}/prep", json={"arrival_action": "arrived"})
        assert arrived.status_code == 200, arrived.text
        warmed = operator.patch(f"/bookings/{booking_id}/prep", json={"warmup_state": "warmed_up"})
        assert warmed.status_code == 200, warmed.text
        assert warmed.json()["status"] == "arrived"
        handoff = operator.patch(f"/bookings/{booking_id}/status", json={"status": "ready"})
        assert handoff.status_code == 200, handoff.text

    def timer(self, action, *, role="pilot", booking_id="scenario-ride"):
        return self.client(role).post(f"/bookings/{booking_id}/timer-action", json={"action": action})

    def charge(self, *, amount=1_200_000, method="cash", key="scenario-charge", booking_id="scenario-ride"):
        payload = {
            "booking_id": booking_id,
            "amount_minor": amount,
            "method": method,
            "idempotency_key": key,
            "occurred_at": "2026-06-01T10:00:00+03:00",
        }
        response = self.client("operator").post("/payments", json=payload)
        assert response.status_code == 200, response.text
        return response.json()["payment"]["payment_id"], payload


@pytest.fixture
def scenario(monkeypatch):
    def forbidden_network(*args, **kwargs):
        pytest.fail("Role scenario attempted a real external transport or Sheets initialization")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden_network)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_network)
    monkeypatch.setattr(SheetWrapper, "__init__", forbidden_network)
    value = Scenario()
    monkeypatch.setattr("apps.api.app.services.shift_timer._now", lambda now=None: now or value.now)
    yield value
    for client in value.clients.values():
        client.close()
    value.app.dependency_overrides.clear()


@pytest.mark.parametrize("role", STAFF)
@pytest.mark.parametrize(
    "path,allowed",
    [
        (f"/bookings?date={DAY}", {"admin", "operator", "pilot", "coach"}),
        ("/clients", {"admin", "operator", "coach"}),
        ("/payments?booking_id=scenario-ride", {"admin", "operator"}),
        (f"/kpi/summary?period=day&date_from={DAY}", set(STAFF)),
    ],
)
def test_role_reads_do_not_mutate_operational_state(scenario, role, path, allowed):
    scenario.booking()
    client = scenario.client(role)
    before = deepcopy(scenario.sheet.tabs)
    response = client.get(path)
    assert response.status_code == (200 if role in allowed else 403), response.text
    assert scenario.sheet.tabs == before


@pytest.mark.parametrize("role", STAFF)
@pytest.mark.parametrize(
    "operation,allowed",
    [
        ("prep", {"admin", "operator", "pilot"}),
        ("start", {"admin", "pilot"}),
        ("charge", {"admin", "operator"}),
        ("refund", {"admin"}),
        ("close", {"admin"}),
    ],
)
def test_role_mutations_enforce_access_before_side_effects(scenario, role, operation, allowed):
    scenario.booking()
    scenario.ready()
    payment_id, _ = scenario.charge()
    client = scenario.client(role)
    before = deepcopy(scenario.sheet.tabs)
    requests = {
        "prep": ("PATCH", "/bookings/scenario-ride/prep", {"warmup_state": "no_warmup"}),
        "start": ("POST", "/bookings/scenario-ride/timer-action", {"action": "start"}),
        "charge": (
            "POST",
            "/payments",
            {
                "booking_id": "scenario-ride",
                "amount_minor": 100,
                "method": "sbp",
                "idempotency_key": "role-extra-charge",
            },
        ),
        "refund": (
            "POST",
            f"/payments/{payment_id}/refunds",
            {"amount_minor": 100, "idempotency_key": "role-refund-key"},
        ),
        "close": ("POST", "/payments/reconciliation/close", {"date": DAY, "counted_total_minor": 1_200_000}),
    }
    method, path, payload = requests[operation]
    response = client.request(method, path, json=payload)
    assert response.status_code == (200 if role in allowed else 403), response.text
    if role not in allowed:
        assert scenario.sheet.tabs == before


def test_admin_demotion_revokes_write_permission_without_logging_in_again(scenario):
    scenario.booking()
    payment_id, _ = scenario.charge()
    admin = scenario.client("admin")
    staff = next(row for row in scenario.sheet.tabs["staff_users"] if row["staff_user_id"] == "staff_admin")
    staff["role"] = "marketing_read"
    before = deepcopy(scenario.sheet.tabs)
    response = admin.post(
        f"/payments/{payment_id}/refunds",
        json={"amount_minor": 100, "idempotency_key": "demoted-refund-key"},
    )
    assert response.status_code == 403, response.text
    assert scenario.sheet.tabs == before


def test_coach_live_focus_stays_with_assigned_session(scenario):
    scenario.booking("unassigned-ride")
    scenario.booking("coach-ride", time="11:00", client_id="client_2", coach_required=True, coach_user_id="staff_coach")
    coach = scenario.client("coach")
    bookings = coach.get(f"/bookings?date={DAY}")
    assert bookings.status_code == 200
    assert [item["booking_id"] for item in bookings.json()] == ["coach-ride"]
    live = coach.get(f"/shift/live?date={DAY}")
    assert live.status_code == 200
    assert live.json()["focus_booking"]["booking_id"] == "coach-ride", live.text


def test_unassigned_pilot_live_focus_does_not_expose_another_pilots_client(scenario):
    scenario.booking()
    pilot = scenario.client("pilot")
    scenario.sheet.tabs["boats"][0]["pilot_user_id"] = "other-pilot"
    listed = pilot.get(f"/bookings?date={DAY}")
    assert listed.status_code == 200
    assert listed.json() == []
    live = pilot.get(f"/shift/live?date={DAY}")
    assert live.status_code == 200
    assert live.json()["focus_booking"] is None, live.text


def test_one_boat_pilot_reassignment_revokes_stale_session_timer_access(scenario):
    scenario.booking()
    scenario.ready()
    old_pilot = scenario.client("pilot")
    second = deepcopy(next(row for row in scenario.sheet.tabs["staff_users"] if row["role"] == "pilot"))
    second.update(staff_user_id="pilot-replacement", phone="+79990000006")
    scenario.sheet.tabs["staff_users"].append(second)
    scenario.sheet.tabs["boats"][0]["pilot_user_id"] = second["staff_user_id"]
    before = deepcopy(scenario.sheet.tabs)
    denied = old_pilot.post("/bookings/scenario-ride/timer-action", json={"action": "start"})
    assert denied.status_code == 403, denied.text
    assert scenario.sheet.tabs == before
    with TestClient(scenario.app) as replacement:
        requested = replacement.post(
            "/auth/request-code", json={"staff_user_id": second["staff_user_id"], "phone": second["phone"]}
        )
        assert requested.status_code == 200, requested.text
        verified = replacement.post(
            "/auth/verify-code", json={"staff_user_id": second["staff_user_id"], "code": requested.json()["debug_code"]}
        )
        assert verified.status_code == 200, verified.text
        assert replacement.post("/bookings/scenario-ride/timer-action", json={"action": "start"}).status_code == 200


@pytest.mark.parametrize("warmup_state", ["warmed_up", "no_warmup"])
def test_handoff_pause_stop_and_lost_response_retries_preserve_elapsed_time(scenario, warmup_state):
    scenario.booking()
    operator = scenario.client("operator")
    assert operator.patch("/bookings/scenario-ride/prep", json={"arrival_action": "arrived"}).status_code == 200
    warmed = operator.patch("/bookings/scenario-ride/prep", json={"warmup_state": warmup_state})
    assert warmed.status_code == 200
    assert warmed.json()["status"] == "arrived"
    assert scenario.timer("start").status_code == 409
    assert operator.patch("/bookings/scenario-ride/status", json={"status": "ready"}).status_code == 200
    assert scenario.timer("start").status_code == 200
    before = deepcopy(scenario.sheet.tabs)
    assert scenario.timer("start").status_code == 409
    assert scenario.sheet.tabs == before
    scenario.now += timedelta(minutes=7)
    paused = scenario.timer("pause")
    assert paused.status_code == 200
    assert paused.json()["elapsed_seconds"] == 420
    before = deepcopy(scenario.sheet.tabs)
    assert scenario.timer("pause").status_code == 409
    assert scenario.sheet.tabs == before
    scenario.now += timedelta(minutes=20)
    stopped = scenario.timer("stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "done"
    assert stopped.json()["actual_duration_seconds"] == 420
    before = deepcopy(scenario.sheet.tabs)
    assert scenario.timer("stop").status_code == 409
    assert scenario.sheet.tabs == before
    kpi = operator.get(f"/kpi/summary?period=day&date_from={DAY}")
    assert kpi.status_code == 200
    assert kpi.json()["sessions_count"] == 1


@pytest.mark.parametrize("status", ["done", "cancelled", "no_show"])
@pytest.mark.parametrize("action", ["start", "pause", "stop", "add_set"])
def test_terminal_booking_timer_actions_are_side_effect_free(scenario, status, action):
    scenario.booking()
    row = scenario.sheet.tabs["bookings"][0]
    row.update(status=status, timer_state="completed" if status == "done" else "idle")
    scenario.client("pilot")
    before = deepcopy(scenario.sheet.tabs)
    response = scenario.timer(action)
    assert response.status_code == 409, response.text
    assert scenario.sheet.tabs == before


def test_invalid_combined_late_and_warmup_does_not_partially_change_booking(scenario):
    scenario.booking()
    before = deepcopy(scenario.sheet.tabs)
    response = scenario.client("operator").patch(
        "/bookings/scenario-ride/prep",
        json={"arrival_action": "late", "warmup_state": "warmed_up"},
    )
    assert response.status_code == 409, response.text
    assert scenario.sheet.tabs == before, "Rejected prep must not persist late status, notices, or audit rows"


@pytest.mark.parametrize("timer_state", ["running", "paused"])
def test_one_boat_cannot_start_next_ride_while_previous_ride_is_active(scenario, timer_state):
    scenario.booking()
    scenario.booking("next-ride", time="11:00", client_id="client_2")
    scenario.ready()
    scenario.ready("next-ride")
    assert scenario.timer("start").status_code == 200
    if timer_state == "paused":
        assert scenario.timer("pause").status_code == 200
    before = deepcopy(scenario.sheet.tabs)
    response = scenario.timer("start", booking_id="next-ride")
    assert response.status_code == 409, "A later slot must not allow a second live ride on the occupied boat"
    assert scenario.sheet.tabs == before


def test_simultaneous_admin_and_pilot_start_get_one_success_per_boat(scenario):
    scenario.booking()
    scenario.booking("next-ride", time="11:00", client_id="client_2")
    scenario.ready()
    scenario.ready("next-ride")
    admin = scenario.client("admin")
    pilot = scenario.client("pilot")
    # Different requests can race even though one boat has only one assigned pilot.
    from threading import Barrier

    barrier = Barrier(2)

    def start(client, booking_id):
        barrier.wait(timeout=10)
        return client.post(f"/bookings/{booking_id}/timer-action", json={"action": "start"}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(start, admin, "scenario-ride"), executor.submit(start, pilot, "next-ride")]
        results = [future.result(timeout=20) for future in futures]
    active = [row for row in scenario.sheet.tabs["bookings"] if row["status"] == "in_progress"]
    assert sorted(results) == [200, 409], {
        "statuses": results,
        "active_booking_ids": [row["booking_id"] for row in active],
    }
    assert len(active) == 1


def test_split_tender_full_refund_retries_match_kpi_and_daily_close(scenario):
    scenario.booking()
    scenario.ready()
    assert scenario.timer("start").status_code == 200
    assert scenario.timer("stop").status_code == 200
    cash_id, cash = scenario.charge(amount=500_000, key="split-cash-charge")
    sbp_id, sbp = scenario.charge(amount=700_000, method="sbp", key="split-sbp-charge")
    for payload in (cash, sbp):
        assert scenario.client("operator").post("/payments", json=payload).status_code == 200
    admin = scenario.client("admin")
    for payment_id, amount in ((cash_id, 500_000), (sbp_id, 700_000)):
        payload = {
            "amount_minor": amount,
            "idempotency_key": f"refund-{payment_id}",
            "occurred_at": "2026-06-01T11:00:00+03:00",
        }
        first = admin.post(f"/payments/{payment_id}/refunds", json=payload)
        replay = admin.post(f"/payments/{payment_id}/refunds", json=payload)
        assert first.status_code == replay.status_code == 200
        assert first.json()["payment"]["payment_id"] == replay.json()["payment"]["payment_id"]
    assert len(scenario.sheet.tabs["payments"]) == 4
    before = deepcopy(scenario.sheet.tabs)
    excess = admin.post(
        f"/payments/{cash_id}/refunds", json={"amount_minor": 1, "idempotency_key": "split-excess-refund"}
    )
    assert excess.status_code == 409
    assert scenario.sheet.tabs == before
    summary = admin.get("/payments/summary?booking_id=scenario-ride").json()
    kpi = admin.get(f"/kpi/summary?period=day&date_from={DAY}").json()
    daily = admin.get(f"/payments/reconciliation/daily?date={DAY}").json()
    assert summary["payment_status"] == "refunded"
    assert summary["net_paid_minor"] == kpi["net_revenue_minor"] == daily["net_received_minor"] == 0
    assert summary["balance_due_minor"] == kpi["outstanding_minor"] == daily["outstanding_minor"] == 1_200_000
    assert kpi["payments_gross_minor"] == daily["charges_minor"] == 1_200_000
    assert kpi["refunds_total_minor"] == daily["refunds_minor"] == 1_200_000
    assert kpi["sessions_count"] == 1
    assert kpi["revenue_estimate"] == 12000
    assert all(method["net_minor"] == 0 for method in daily["methods"])
    closed = admin.post("/payments/reconciliation/close", json={"date": DAY, "counted_total_minor": 0})
    replay = admin.post("/payments/reconciliation/close", json={"date": DAY, "counted_total_minor": 0})
    assert closed.status_code == replay.status_code == 200
    assert closed.json()["closure_id"] == replay.json()["closure_id"]
    assert len(scenario.sheet.tabs["payment_closures"]) == 1


@pytest.mark.parametrize("changed", [{"amount_minor": 1}, {"method": "sbp"}, {"booking_id": "next-ride"}])
def test_payment_retry_with_changed_business_payload_is_rejected(scenario, changed):
    scenario.booking()
    scenario.booking("next-ride", time="11:00", client_id="client_2")
    _, payload = scenario.charge()
    before = deepcopy(scenario.sheet.tabs)
    conflict = scenario.client("operator").post("/payments", json={**payload, **changed})
    assert conflict.status_code == 409, conflict.text
    assert scenario.sheet.tabs == before


def test_payment_persisted_before_timeout_is_recovered_without_losing_audit(scenario, monkeypatch):
    scenario.booking()
    append = scenario.sheet.append_row
    failed_once = False

    def lose_ack(tab_name, row, *, unique_key=None):
        nonlocal failed_once
        append(tab_name, row, unique_key=unique_key)
        if tab_name == "payments" and not failed_once:
            failed_once = True
            raise TimeoutError("simulated lost Sheets write acknowledgement")

    monkeypatch.setattr(scenario.sheet, "append_row", lose_ack)
    payload = {
        "booking_id": "scenario-ride",
        "amount_minor": 1_200_000,
        "method": "cash",
        "idempotency_key": "lost-ack-charge-key",
    }
    first = scenario.client("operator").post("/payments", json=payload)
    assert first.status_code >= 500, first.text
    retry = scenario.client("operator").post("/payments", json=payload)
    assert retry.status_code == 200, retry.text
    assert len(scenario.sheet.tabs["payments"]) == 1
    audit = [row for row in scenario.sheet.tabs["audit_log"] if row["action"] == "payment_recorded"]
    assert len(audit) == 1, "Successful recovery must not leave an unaudited charge"


def test_duplicated_canonical_intake_and_operator_retries_produce_one_entity_each(scenario):
    record = {
        "request_id": "scenario-intake-001",
        "parent_name": "Scenario Rider",
        "phone": "+7 (999) 000-22-33",
        "created_at": "2026-06-01T07:00:00Z",
    }
    scenario.source.tabs["Ruza"] = [record, dict(record)]
    operator = scenario.client("operator")
    first = operator.post("/intake/sync")
    second = operator.post("/intake/sync")
    assert first.status_code == second.status_code == 200
    assert first.json()["created"] == 1
    assert first.json()["skipped_existing"] == 1
    assert second.json()["created"] == 0
    assert len(scenario.sheet.tabs["leads"]) == 1
    assert len([row for row in scenario.sheet.tabs["audit_log"] if row["action"] == "sync_create"]) == 1
    # Intake creates a lead, not a reservation; operator conversion is explicit.
    assert len(scenario.sheet.tabs["clients"]) == 2
    assert scenario.sheet.tabs["bookings"] == []
    created = operator.post("/clients", json={"full_name": "Scenario Rider", "phone": record["phone"]})
    retry = operator.post("/clients", json={"full_name": "Scenario Rider", "phone": "79990002233"})
    assert created.status_code == retry.status_code == 200
    assert created.json()["client_id"] == retry.json()["client_id"]
    assert len(scenario.sheet.tabs["clients"]) == 3
    payload = scenario.booking(client_id=created.json()["client_id"])
    before = deepcopy(scenario.sheet.tabs)
    booked_again = operator.post("/bookings", json=payload)
    assert booked_again.status_code == 200
    assert len(scenario.sheet.tabs["bookings"]) == 1
    assert scenario.sheet.tabs == before
    lead_id = scenario.sheet.tabs["leads"][0]["lead_id"]
    assert operator.patch(f"/leads/{lead_id}/status", json={"status": "booked"}).status_code == 200


def test_operator_retry_with_domestic_russian_phone_does_not_duplicate_client(scenario):
    operator = scenario.client("operator")
    first = operator.post("/clients", json={"full_name": "Scenario Rider", "phone": "+7 (999) 000-22-33"})
    retry = operator.post("/clients", json={"full_name": "Scenario Rider", "phone": "89990002233"})
    assert first.status_code == retry.status_code == 200
    assert first.json()["client_id"] == retry.json()["client_id"], "Russian domestic 8 and E.164 +7 identify one phone"
    assert len(scenario.sheet.tabs["clients"]) == 3


def test_booking_retry_id_cannot_be_reused_for_another_client(scenario):
    payload = scenario.booking()
    before = deepcopy(scenario.sheet.tabs)
    response = scenario.client("operator").post("/bookings", json={**payload, "client_id": "client_2"})
    assert response.status_code == 409, "Conflicting retry must not report the first client's booking as a new success"
    assert scenario.sheet.tabs == before


def test_booking_retry_id_does_not_disclose_foreign_club_booking(scenario):
    scenario.sheet.tabs["bookings"].append(
        {
            "booking_id": "foreign-booking",
            "club_id": "other_club",
            "client_id": "foreign-client",
            "status": "done",
            "total_price": "99000",
        }
    )
    operator = scenario.client("operator")
    before = deepcopy(scenario.sheet.tabs)
    response = operator.post(
        "/bookings",
        json={
            "booking_id": "foreign-booking",
            "client_id": "client_1",
            "date": DAY,
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    assert response.status_code in {404, 409}, "A club-local create must not return another club's status and price"
    assert scenario.sheet.tabs == before


def test_simultaneous_duplicate_start_records_one_start(scenario, monkeypatch):
    from threading import Barrier
    from time import sleep

    from apps.api.app.services import shift_timer

    scenario.booking()
    scenario.ready()
    admin = scenario.client("admin")
    pilot = scenario.client("pilot")
    barrier = Barrier(2)
    get_booking_row = shift_timer.get_booking_row

    def delayed_booking_read(*args, **kwargs):
        row = deepcopy(get_booking_row(*args, **kwargs))
        if row["status"] == "ready":
            # Real Sheets responses can return a snapshot after another request writes.
            sleep(0.5)
        return row

    monkeypatch.setattr(shift_timer, "get_booking_row", delayed_booking_read)

    def start(client):
        barrier.wait(timeout=10)
        return client.post("/bookings/scenario-ride/timer-action", json={"action": "start"}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(start, client) for client in (admin, pilot)]
        results = [future.result(timeout=20) for future in futures]
    starts = [
        row
        for row in scenario.sheet.tabs["audit_log"]
        if row["entity"] == "booking" and "'status': 'in_progress'" in row["diff_json"]
    ]
    assert sorted(results) == [200, 409], {"statuses": results, "start_audit_count": len(starts)}
    assert len(starts) == 1
    assert scenario.sheet.tabs["bookings"][0]["status"] == "in_progress"


@pytest.mark.parametrize("attempt", range(3))
def test_concurrent_add_set_and_new_booking_cannot_both_take_next_slot(scenario, attempt, monkeypatch):
    from threading import Barrier, Event
    from time import sleep

    from apps.api.app.services import shift_timer
    from apps.api.app.services.ride_runtime import iter_booking_slots

    scenario.booking()
    scenario.ready()
    assert scenario.timer("start").status_code == 200
    pilot = scenario.client("pilot")
    operator = scenario.client("operator")
    barrier = Barrier(2)
    availability_checked = Event()
    next_slot_available = shift_timer._next_slot_available

    def delayed_availability(*args, **kwargs):
        available = next_slot_available(*args, **kwargs)
        availability_checked.set()
        # Simulate a slow Sheets response after its free-capacity snapshot.
        # A shared boat lock may serialize reserve() without waiting on it here.
        sleep(0.5)
        return available

    monkeypatch.setattr(shift_timer, "_next_slot_available", delayed_availability)

    def extend():
        barrier.wait(timeout=10)
        return pilot.post("/bookings/scenario-ride/timer-action", json={"action": "add_set"}).status_code

    def reserve():
        barrier.wait(timeout=10)
        assert availability_checked.wait(timeout=10), "Pilot did not reach the capacity check"
        return operator.post(
            "/bookings",
            json={
                "booking_id": f"extension-race-{attempt}",
                "client_id": "client_2",
                "date": DAY,
                "time": "10:30",
                "boat_id": "boat_1",
            },
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(extend), executor.submit(reserve)]
        results = [future.result(timeout=20) for future in futures]
    occupying = [
        row["booking_id"]
        for row in scenario.sheet.tabs["bookings"]
        if row["status"] not in {"cancelled", "no_show"} and "10:30" in iter_booking_slots(row)
    ]
    assert sorted(results) == [200, 409], {"add_set_create_statuses": results, "next_slot_occupants": occupying}
    assert len(occupying) == 1, occupying
