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


def test_auth_phone_only_login() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)

    request_code = client.post("/auth/request-code", json={"phone": "+79990000001"})
    assert request_code.status_code == 200
    body = request_code.json()
    assert body["staff_user_id"] == "staff_001"
    assert body["full_name"] == "Operator One"

    verify = client.post("/auth/verify-code", json={"phone": "89990000001", "code": body["debug_code"]})
    assert verify.status_code == 200
    assert verify.json()["role"] == "operator"
    app.dependency_overrides.clear()


def test_booking_wetsuit_and_ride_type_persist() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)

    response = client.post(
        "/bookings",
        json={
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "ride_type": "surf",
            "wetsuit_required": True,
            "wetsuit_size": "L",
            "wetsuit_gender": "female",
        },
    )
    assert response.status_code == 200
    booking_id = response.json()["booking_id"]
    listed = client.get("/bookings?date=2026-06-01").json()
    item = next(row for row in listed if row["booking_id"] == booking_id)
    assert item["ride_type"] == "surf"
    assert item["wetsuit_required"] is True
    assert item["wetsuit_size"] == "L"
    assert item["wetsuit_gender"] == "female"
    app.dependency_overrides.clear()


def test_checkin_ready_requires_arrived() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client)
    client.post(
        "/bookings",
        json={
            "booking_id": "bkg_ready_gate",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    skipped = client.post(
        "/checkins",
        json={"method": "phone", "phone": "+79990000011", "date": "2026-06-01", "status": "ready"},
    )
    assert skipped.status_code == 409
    assert mock_sheet.read_tab("checkins") == []
    app.dependency_overrides.clear()


def test_kpi_counts_done_sessions_only() -> None:
    mock_sheet = MockSheetWrapper()
    client = _make_client(mock_sheet)
    _login(client, staff_user_id="staff_admin", phone="+79990000000")

    client.post(
        "/bookings",
        json={
            "booking_id": "bkg_kpi_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
        },
    )
    empty = client.get("/kpi/summary?period=day&date_from=2026-06-01").json()
    assert empty["sessions_count"] == 0

    operator = _make_client(mock_sheet)
    _login(operator)
    operator.patch("/bookings/bkg_kpi_1/status", json={"status": "arrived"})
    operator.patch("/bookings/bkg_kpi_1/status", json={"status": "ready"})
    operator.patch("/bookings/bkg_kpi_1/status", json={"status": "in_progress"})
    operator.patch("/bookings/bkg_kpi_1/status", json={"status": "done"})

    filled = client.get("/kpi/summary?period=day&date_from=2026-06-01").json()
    assert filled["sessions_count"] == 1
    assert filled["revenue_estimate"] == 12000
    assert filled["utilization_pct"] == 100.0
    app.dependency_overrides.clear()


def test_marketing_funnel_contacted_includes_booked() -> None:
    mock_sheet = MockSheetWrapper()
    mock_sheet.tabs["leads"] = [
        {
            "lead_id": "lead_1",
            "club_id": "ice_beach_ruza",
            "full_name": "A",
            "phone": "7999",
            "source": "ig",
            "status": "new",
            "created_at": "2026-06-02T00:00:00Z",
        },
        {
            "lead_id": "lead_2",
            "club_id": "ice_beach_ruza",
            "full_name": "B",
            "phone": "7998",
            "source": "ig",
            "status": "booked",
            "created_at": "2026-06-03T00:00:00Z",
        },
    ]
    client = _make_client(mock_sheet)
    _login(client, staff_user_id="staff_admin", phone="+79990000000")
    funnel = client.get("/marketing/funnel?date_from=2026-06-01&date_to=2026-06-30").json()
    assert funnel["leads_count"] == 2
    assert funnel["booked_count"] == 1
    assert funnel["contacted_count"] == 1
    app.dependency_overrides.clear()


def test_boats_list_and_pilot_cannot_change_foreign_boat() -> None:
    mock_sheet = MockSheetWrapper()
    mock_sheet.tabs["boats"].append(
        {
            "boat_id": "boat_2",
            "club_id": "ice_beach_ruza",
            "boat_name": "Axis B",
            "capacity_default": "1",
            "pilot_user_id": "someone_else",
            "is_active": "true",
        }
    )
    mock_sheet.tabs["bookings"].append(
        {
            "booking_id": "bkg_boat2",
            "club_id": "ice_beach_ruza",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "11:00",
            "boat_id": "boat_2",
            "status": "ready",
            "total_price": "12000",
            "created_by": "staff_001",
            "created_at": "2026-06-01T07:00:00Z",
            "updated_at": "2026-06-01T07:10:00Z",
            "coach_required": "false",
            "coach_user_id": "",
            "ride_type": "wakeboard",
            "wetsuit_required": "false",
            "wetsuit_size": "",
            "wetsuit_gender": "",
            "notes": "",
        }
    )
    client = _make_client(mock_sheet)
    _login(client)
    boats = client.get("/boats").json()
    assert [row["boat_id"] for row in boats] == ["boat_1", "boat_2"]

    pilot = _make_client(mock_sheet)
    _login(pilot, staff_user_id="staff_pilot", phone="+79990000002")
    forbidden = pilot.patch("/bookings/bkg_boat2/status", json={"status": "in_progress"})
    assert forbidden.status_code == 403
    own_boats = pilot.get("/boats").json()
    assert [row["boat_id"] for row in own_boats] == ["boat_1"]
    app.dependency_overrides.clear()
