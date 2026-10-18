"""Нет вкладки clubs в Таблице: API не должен падать 400, таймзона — Europe/Moscow.

Повторяет прод-инцидент 18.10: Google Sheets на чтение отсутствующей вкладки отвечает
HttpError 400 "Unable to parse range: clubs!A:ZZ", а API превращал это в
400 "Missing or misnamed sheet tab: clubs" для напоминаний смены, отметки опозданий,
/kpi/summary, snapshot и daily brief.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import httplib2
import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.checkins import mark_late_checkins
from apps.api.app.services.preflight import run_preflight_check
from apps.api.app.services.shift import club_local_today, club_timezone_name
from apps.api.app.services.shift_timer import _club_zone, process_shift_reminders
from packages.sheets import SheetWrapper
from packages.sheets.memory import demo_tabs

from conftest import MockSheetWrapper, make_test_settings

CLUB_ID = "ice_beach_ruza"
AGENTS_HEADERS = {"X-Agents-Secret": "test-agents-secret"}


def _missing_tab_error(tab_name: str) -> HttpError:
    resp = httplib2.Response({"status": 400})
    resp.reason = "Bad Request"
    uri = f"https://sheets.googleapis.com/v4/spreadsheets/test-sheet/values/{tab_name}%21A%3AZZ?alt=json"
    content = f'{{"error": {{"code": 400, "message": "Unable to parse range: {tab_name}!A:ZZ"}}}}'.encode()
    return HttpError(resp, content, uri=uri)


class ProdLikeSheet(MockSheetWrapper):
    """In-memory Таблица, которая на отсутствующую вкладку отвечает как Google Sheets API."""

    # Настоящий хелпер SheetWrapper, а не упрощённая in-memory версия.
    read_optional_tab = SheetWrapper.read_optional_tab

    def read_tab(self, tab_name: str) -> list[dict[str, str]]:
        if tab_name not in self.tabs:
            raise _missing_tab_error(tab_name)
        return super().read_tab(tab_name)

    def _fetch_values(self, tab_name: str) -> list[list[str]]:
        if tab_name not in self.tabs:
            raise _missing_tab_error(tab_name)
        return super()._fetch_values(tab_name)

    def get_headers(self, tab_name: str) -> list[str] | None:
        if tab_name not in self.tabs:
            return None
        return super().get_headers(tab_name)


def _sheet_without_clubs(tabs: dict | None = None) -> ProdLikeSheet:
    sheet = ProdLikeSheet(tabs)
    sheet.tabs.pop("clubs", None)
    return sheet


def _agents_client(sheet: MockSheetWrapper) -> TestClient:
    app.dependency_overrides[get_sheet_wrapper] = lambda: sheet
    app.dependency_overrides[get_settings] = make_test_settings
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_prod_like_sheet_reproduces_missing_tab_error() -> None:
    sheet = _sheet_without_clubs()
    with pytest.raises(HttpError):
        sheet.read_tab("clubs")
    assert sheet.read_optional_tab("clubs") == []


def test_club_timezone_falls_back_to_moscow_without_clubs_tab() -> None:
    sheet = _sheet_without_clubs()
    assert club_timezone_name(sheet, CLUB_ID) is None
    assert _club_zone(sheet, CLUB_ID) == ZoneInfo("Europe/Moscow")
    assert club_local_today(sheet, CLUB_ID) == datetime.now(ZoneInfo("Europe/Moscow")).date()


def test_shift_reminders_without_clubs_tab_do_not_fail() -> None:
    sheet = _sheet_without_clubs()
    now = datetime(2026, 6, 1, 9, 50, tzinfo=ZoneInfo("Europe/Moscow"))
    result = process_shift_reminders(
        sheet, make_test_settings(), club_id=CLUB_ID, actor_staff_user_id="system-agent", now=now
    )
    assert isinstance(result, dict)

    client = _agents_client(sheet)
    response = client.post("/internal/agents/shift-reminders", headers=AGENTS_HEADERS)
    assert response.status_code == 200, response.text


def test_mark_late_without_clubs_tab_do_not_fail() -> None:
    sheet = _sheet_without_clubs()
    result = mark_late_checkins(
        sheet, club_id=CLUB_ID, target_date="2026-06-01", actor_staff_user_id="system-agent"
    )
    assert result["marked_late"] >= 0

    client = _agents_client(sheet)
    response = client.post("/internal/agents/mark-late", headers=AGENTS_HEADERS)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/internal/agents/snapshot"),
        ("get", "/internal/agents/daily-brief?mode=morning"),
        ("get", "/internal/agents/preflight"),
    ],
)
def test_agent_endpoints_without_clubs_tab_do_not_return_400(method: str, path: str) -> None:
    sheet = _sheet_without_clubs(demo_tabs(today=datetime.now(ZoneInfo("Europe/Moscow")).date()))
    client = _agents_client(sheet)
    response = getattr(client, method)(path, headers=AGENTS_HEADERS)
    assert response.status_code == 200, response.text
    assert "Missing or misnamed sheet tab" not in response.text


def test_other_missing_tabs_still_fail_loudly() -> None:
    """Fallback только для clubs: отсутствие критичной вкладки по-прежнему 400."""
    sheet = _sheet_without_clubs()
    sheet.tabs.pop("bookings")
    client = _agents_client(sheet)
    response = client.post("/internal/agents/shift-reminders", headers=AGENTS_HEADERS)
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing or misnamed sheet tab: bookings"


def test_preflight_warns_when_clubs_tab_missing() -> None:
    sheet = _sheet_without_clubs(demo_tabs(today=date(2026, 6, 1)))
    summary = run_preflight_check(sheet, target_date="2026-06-01", public_club_id=CLUB_ID)
    codes = {item["code"]: item for item in summary["checks"]}
    assert summary["blockers"] == 0
    assert codes["clubs:tab"]["level"] == "WARN"
    assert "Europe/Moscow" in codes["clubs:tab"]["message"]
    assert summary["warnings"] >= 1


def test_preflight_warns_when_clubs_has_no_row_for_public_club() -> None:
    tabs = demo_tabs(today=date(2026, 6, 1))
    tabs["clubs"] = [
        {"club_id": "other_club", "club_name": "Other", "timezone": "Europe/Moscow", "is_active": "true"}
    ]
    sheet = ProdLikeSheet(tabs)
    summary = run_preflight_check(sheet, target_date="2026-06-01", public_club_id=CLUB_ID)
    codes = {item["code"]: item["level"] for item in summary["checks"]}
    assert summary["blockers"] == 0
    assert codes["clubs:row"] == "WARN"


def test_preflight_warns_on_invalid_timezone() -> None:
    tabs = demo_tabs(today=date(2026, 6, 1))
    tabs["clubs"] = [{"club_id": CLUB_ID, "club_name": "Ruza", "timezone": "Mars/Base", "is_active": "true"}]
    summary = run_preflight_check(ProdLikeSheet(tabs), target_date="2026-06-01", public_club_id=CLUB_ID)
    codes = {item["code"]: item["level"] for item in summary["checks"]}
    assert codes["clubs:timezone"] == "WARN"


def test_preflight_passes_when_clubs_row_present() -> None:
    sheet = ProdLikeSheet(demo_tabs(today=date(2026, 6, 1)))
    summary = run_preflight_check(sheet, target_date="2026-06-01", public_club_id=CLUB_ID)
    codes = {item["code"]: item["level"] for item in summary["checks"]}
    assert codes["clubs:row"] == "PASS"
    assert "clubs:tab" not in codes


def test_admin_preflight_route_reports_clubs_warning() -> None:
    sheet = _sheet_without_clubs(demo_tabs(today=date(2026, 6, 1)))
    client = _agents_client(sheet)
    request_code = client.post("/auth/request-code", json={"staff_user_id": "staff_admin", "phone": "+79990000000"})
    assert request_code.status_code == 200
    verify = client.post(
        "/auth/verify-code", json={"staff_user_id": "staff_admin", "code": request_code.json()["debug_code"]}
    )
    assert verify.status_code == 200
    response = client.get("/preflight/summary?date=2026-06-01")
    assert response.status_code == 200, response.text
    codes = {item["code"]: item["level"] for item in response.json()["checks"]}
    assert codes["clubs:tab"] == "WARN"
