from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from conftest import MockSheetWrapper, make_test_settings


def _client(sheet: MockSheetWrapper) -> TestClient:
    app.dependency_overrides[get_sheet_wrapper] = lambda: sheet
    app.dependency_overrides[get_settings] = make_test_settings
    return TestClient(app)


def _login(client: TestClient, staff_user_id: str = "staff_001", phone: str = "+79990000001") -> None:
    request = client.post("/auth/request-code", json={"staff_user_id": staff_user_id, "phone": phone})
    code = request.json()["debug_code"]
    response = client.post("/auth/verify-code", json={"staff_user_id": staff_user_id, "code": code})
    assert response.status_code == 200


def _create_booking(client: TestClient) -> None:
    response = client.post(
        "/bookings",
        json={
            "booking_id": "bkg_payment_1",
            "client_id": "client_1",
            "date": "2026-06-01",
            "time": "10:00",
            "boat_id": "boat_1",
            "ride_type": "surf",
        },
    )
    assert response.status_code == 200


def test_payment_is_idempotent_and_enriches_booking() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client)
    _create_booking(client)

    payload = {
        "booking_id": "bkg_payment_1",
        "amount_minor": 1_200_000,
        "method": "sbp",
        "idempotency_key": "payment-test-key-1",
        "occurred_at": "2026-06-01T09:55:00+03:00",
    }
    first = client.post("/payments", json=payload)
    second = client.post("/payments", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["payment"]["payment_id"] == second.json()["payment"]["payment_id"]
    assert first.json()["payment"]["paid_at"] == "2026-06-01T09:55:00+03:00"
    assert sheet.read_tab("payments")[0]["paid_at"] == "2026-06-01T09:55:00+03:00"
    assert len(sheet.read_tab("payments")) == 1
    assert first.json()["summary"]["payment_status"] == "paid"

    bookings = client.get("/bookings?date=2026-06-01")
    assert bookings.status_code == 200
    assert bookings.json()[0]["payment_status"] == "paid"
    assert bookings.json()[0]["balance_due_minor"] == 0

    app.dependency_overrides.clear()


def test_refund_guard_and_daily_reconciliation() -> None:
    sheet = MockSheetWrapper()
    operator = _client(sheet)
    _login(operator)
    _create_booking(operator)
    charge = operator.post(
        "/payments",
        json={
            "booking_id": "bkg_payment_1",
            "amount_minor": 1_200_000,
            "method": "card_terminal",
            "idempotency_key": "payment-test-key-2",
        },
    )
    payment_id = charge.json()["payment"]["payment_id"]

    operator.post("/auth/logout")
    _login(operator, "staff_admin", "+79990000000")
    refund = operator.post(
        f"/payments/{payment_id}/refunds",
        json={"amount_minor": 200_000, "idempotency_key": "refund-test-key-1"},
    )
    assert refund.status_code == 200
    assert refund.json()["summary"]["payment_status"] == "partially_refunded"

    excessive = operator.post(
        f"/payments/{payment_id}/refunds",
        json={"amount_minor": 1_100_000, "idempotency_key": "refund-test-key-2"},
    )
    assert excessive.status_code == 409

    reconciliation = operator.get("/payments/reconciliation/daily?date=2026-06-01")
    assert reconciliation.status_code == 200
    assert reconciliation.json()["net_received_minor"] == 1_000_000
    assert reconciliation.json()["outstanding_minor"] == 200_000

    mismatch = operator.post(
        "/payments/reconciliation/close",
        json={"date": "2026-06-01", "counted_total_minor": 900_000},
    )
    assert mismatch.status_code == 409
    closed = operator.post(
        "/payments/reconciliation/close",
        json={
            "date": "2026-06-01",
            "counted_total_minor": 900_000,
            "override_discrepancy": True,
            "notes": "Тестовая сверка",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["discrepancy_minor"] == -100_000

    app.dependency_overrides.clear()


def test_payment_rbac_and_kpi_real_money() -> None:
    sheet = MockSheetWrapper()
    client = _client(sheet)
    _login(client, "staff_pilot", "+79990000002")
    denied = client.post(
        "/payments",
        json={
            "booking_id": "missing",
            "amount_minor": 100,
            "method": "cash",
            "idempotency_key": "payment-test-key-3",
        },
    )
    assert denied.status_code == 403

    app.dependency_overrides.clear()
