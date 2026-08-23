from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.config import get_settings
from apps.api.app.main import app

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


def test_auth_code_flow_and_me() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)

    _login(client)

    response = client.get("/auth/me")
    assert response.status_code == 200
    payload = response.json()
    assert payload["staff_user_id"] == "staff_001"
    assert payload["role"] == "operator"

    audits = mock_sheet.read_tab("audit_log")
    assert any(row["action"] == "request_login_code" for row in audits)
    assert any(row["action"] == "login_success" for row in audits)

    app.dependency_overrides.clear()


def test_availability_contract() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    response = client.get("/availability?date=2026-06-01")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["boat_id"] == "boat_1"
    assert payload[0]["time"] == "10:00"
    assert payload[0]["capacity"] == 1
    assert payload[0]["available"] == 1

    app.dependency_overrides.clear()


def test_booking_contract_writes_audit_and_price() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    response = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_test_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "coach_required": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["booking_id"] == "bkg_test_1"
    assert body["status"] == "confirmed"
    assert body["total_price"] == 15500

    bookings = mock_sheet.read_tab("bookings")
    assert len(bookings) == 1
    assert bookings[0]["booking_id"] == "bkg_test_1"
    assert bookings[0]["total_price"] == "15500"

    audits = mock_sheet.read_tab("audit_log")
    assert any(audit["action"] == "create" and audit["entity"] == "booking" for audit in audits)

    app.dependency_overrides.clear()


def test_booking_no_overbook() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    payload = {
        "client_id": "client_1",
        "date": "2026-06-01",
        "time": "10:00",
        "boat_id": "boat_1",
        "coach_required": False,
    }

    first = client.post("/bookings", json=payload)
    assert first.status_code == 200

    second = client.post("/clients", json={"full_name": "Client Two", "phone": "+79990000012"})
    assert second.status_code == 200
    client_id = second.json()["client_id"]

    second_booking = client.post("/bookings", json={**payload, "client_id": client_id})
    assert second_booking.status_code == 409
    detail = second_booking.json().get("detail", "")
    assert "capacity" in detail.lower() or "no capacity" in detail.lower()

    app.dependency_overrides.clear()


def test_booking_status_transition_and_pilot_queue() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    create_response = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_test_2",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "coach_required": False,
        },
    )
    assert create_response.status_code == 200

    arrived = client.patch("/bookings/bkg_test_2/status", json={"status": "arrived"})
    assert arrived.status_code == 200
    ready = client.patch("/bookings/bkg_test_2/status", json={"status": "ready"})
    assert ready.status_code == 200

    pilot_client = _make_client(mock_sheet)
    _login(pilot_client, staff_user_id="staff_pilot", phone="+79990000002")
    queue = pilot_client.get("/pilot/today?date=2026-06-01")
    assert queue.status_code == 200
    payload = queue.json()
    assert payload[0]["booking_id"] == "bkg_test_2"
    assert payload[0]["client_name"] == "Client One"
    assert payload[0]["status"] == "ready"

    in_progress = pilot_client.patch("/bookings/bkg_test_2/status", json={"status": "in_progress"})
    assert in_progress.status_code == 200
    done = pilot_client.patch("/bookings/bkg_test_2/status", json={"status": "done"})
    assert done.status_code == 200

    app.dependency_overrides.clear()


def test_booking_rbac_pilot_forbidden() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client, staff_user_id="staff_pilot", phone="+79990000002")

    response = client.post(
        "/bookings",
        json={
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "coach_required": False,
        },
    )
    assert response.status_code == 403

    app.dependency_overrides.clear()


def test_checkin_by_phone() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    create_response = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_checkin_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "coach_required": False,
        },
    )
    assert create_response.status_code == 200

    checkin = client.post(
        "/checkins",
        json={"method": "phone", "phone": "+79990000011", "date": "2026-06-01", "status": "arrived"},
    )
    assert checkin.status_code == 200
    body = checkin.json()
    assert body["booking_id"] == "bkg_checkin_1"
    assert body["status"] == "arrived"

    booking = client.get("/bookings?date=2026-06-01").json()
    assert booking[0]["status"] == "arrived"
    assert len(mock_sheet.read_tab("checkins")) == 1

    app.dependency_overrides.clear()


def test_checkin_mark_late() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    client.post(
        "/bookings",
        json={
            "booking_id": "bkg_late_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "coach_required": False,
        },
    )

    response = client.post("/checkins/mark-late?date=2026-06-01&minutes_before=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["marked_late"] >= 1

    bookings = client.get("/bookings?date=2026-06-01").json()
    late_booking = next(item for item in bookings if item["booking_id"] == "bkg_late_1")
    assert late_booking["status"] == "late"

    app.dependency_overrides.clear()
