from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_intake_sheet_wrapper, get_sheet_wrapper
from apps.api.app.main import app

from conftest import MockSheetWrapper, make_test_settings


def _source_sheet() -> MockSheetWrapper:
    return MockSheetWrapper(
        {
            "Ruza": [
                {
                    "created_at": "2026-08-24T08:00:00Z",
                    "request_id": "req-ruza-001",
                    "source_cta": "website",
                    "requester_role": "parent",
                    "parent_name": "Анна Тестова",
                    "phone": "+7 (999) 000-11-22",
                    "child_name": "Иван Тестов",
                    "goal": "Первое катание за катером",
                    "package": "Пробная тренировка",
                    "utm_source": "mywavewake.ru",
                    "utm_campaign": "ruza_launch",
                    "status": "new",
                },
                {
                    "request_id": "req-invalid-phone",
                    "parent_name": "Нет Телефона",
                    "phone": "123",
                },
            ]
        }
    )


def _login(client: TestClient) -> None:
    requested = client.post(
        "/auth/request-code",
        json={"staff_user_id": "staff_001", "phone": "+79990000001"},
    )
    assert requested.status_code == 200
    verified = client.post(
        "/auth/verify-code",
        json={"staff_user_id": "staff_001", "code": requested.json()["debug_code"]},
    )
    assert verified.status_code == 200


def test_authenticated_intake_sync_is_idempotent() -> None:
    source = _source_sheet()
    target = MockSheetWrapper()
    app.dependency_overrides[get_intake_sheet_wrapper] = lambda: source
    app.dependency_overrides[get_sheet_wrapper] = lambda: target
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)
    _login(client)

    first = client.post("/intake/sync")
    assert first.status_code == 200
    assert first.json() == {
        "source_tab": "Ruza",
        "scanned": 2,
        "created": 1,
        "skipped_existing": 0,
        "skipped_invalid": 1,
        "errors": [],
    }
    lead = target.tabs["leads"][0]
    assert lead["external_source"] == "mywave_canonical_ruza"
    assert lead["external_record_id"] == "req-ruza-001"
    assert lead["phone"] == "79990001122"
    assert lead["utm_source"] == "mywavewake.ru"
    assert "Спортсмен: Иван Тестов" in lead["notes"]

    second = client.post("/intake/sync")
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["skipped_existing"] == 1
    assert len(target.tabs["leads"]) == 1
    app.dependency_overrides.clear()


def test_agents_intake_sync_requires_secret() -> None:
    source = _source_sheet()
    target = MockSheetWrapper()
    app.dependency_overrides[get_intake_sheet_wrapper] = lambda: source
    app.dependency_overrides[get_sheet_wrapper] = lambda: target
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)

    denied = client.post("/internal/agents/intake-sync")
    assert denied.status_code == 401
    allowed = client.post(
        "/internal/agents/intake-sync",
        headers={"X-Agents-Secret": "test-agents-secret"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["created"] == 1
    app.dependency_overrides.clear()


def test_public_booking_request_writes_canonical_source_then_lead() -> None:
    source = MockSheetWrapper({"Ruza": []})
    target = MockSheetWrapper()
    app.dependency_overrides[get_intake_sheet_wrapper] = lambda: source
    app.dependency_overrides[get_sheet_wrapper] = lambda: target
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)

    response = client.post(
        "/public/booking-request",
        json={
            "full_name": "Мария Райдер",
            "phone": "+7 999 111-22-33",
            "date": "2026-06-15",
            "time": "12:30",
            "ride_type": "surf",
            "notes": "Первая тренировка",
        },
    )
    assert response.status_code == 200
    assert len(source.tabs["Ruza"]) == 1
    source_row = source.tabs["Ruza"][0]
    assert source_row["source_cta"] == "ruza_public_widget"
    assert "2026-06-15 12:30" in source_row["notes"]
    assert len(target.tabs["leads"]) == 1
    assert target.tabs["leads"][0]["external_record_id"] == source_row["request_id"]
    assert response.json()["lead_id"] == target.tabs["leads"][0]["lead_id"]
    app.dependency_overrides.clear()
