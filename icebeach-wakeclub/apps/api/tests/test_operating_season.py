from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.kpi import _get_period_bounds
from apps.api.app.services.operating_calendar import is_in_season

from conftest import MockSheetWrapper, make_test_settings


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 4, 30), False),
        (date(2026, 5, 1), True),  # первый рабочий день сезона
        (date(2026, 6, 1), True),
        (date(2026, 9, 25), True),  # последний рабочий день сезона (включительно)
        (date(2026, 9, 26), False),
        (date(2026, 10, 1), False),
    ],
)
def test_season_is_may_1_to_sep_25_inclusive(value: date, expected: bool) -> None:
    assert is_in_season(value) is expected


def test_kpi_season_period_matches_operating_season() -> None:
    start, end = _get_period_bounds("season", today=date(2026, 7, 15), date_from=None, date_to=None)
    assert start == date(2026, 5, 1)
    assert end == date(2026, 9, 25)


def _make_client(mock_sheet: MockSheetWrapper) -> TestClient:
    app.dependency_overrides[get_sheet_wrapper] = lambda: mock_sheet
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)
    request_code = client.post("/auth/request-code", json={"staff_user_id": "staff_001", "phone": "+79990000001"})
    assert request_code.status_code == 200
    verify = client.post(
        "/auth/verify-code", json={"staff_user_id": "staff_001", "code": request_code.json()["debug_code"]}
    )
    assert verify.status_code == 200
    return client


def test_availability_respects_season_bounds() -> None:
    client = _make_client(MockSheetWrapper())
    try:
        # Минимальный seed (packages/sheets/memory.py) открывает слоты только по понедельникам (weekday=0).
        # 2026-05-04 — первый понедельник сезона, 2026-09-21 — последний понедельник сезона,
        # 2026-04-27 и 2026-09-28 — понедельники вне сезона.
        assert len(client.get("/availability?date=2026-05-04").json()) > 0
        assert len(client.get("/availability?date=2026-09-21").json()) > 0
        assert client.get("/availability?date=2026-04-27").json() == []
        assert client.get("/availability?date=2026-09-28").json() == []
    finally:
        app.dependency_overrides.clear()
