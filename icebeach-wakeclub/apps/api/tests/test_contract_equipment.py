"""«Как в прошлый раз»: инвентарь, выдача снаряжения, last_time, роли, миграция."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.services.preflight import run_preflight_check
from packages.sheets import demo_tabs
from packages.sheets.schema import TAB_SCHEMAS, migration_columns

from conftest import MockSheetWrapper, make_test_settings

TODAY = date(2026, 6, 1)
PHONES = {
    "staff_001": "+79990000001",
    "staff_pilot": "+79990000002",
    "staff_coach": "+79990000003",
    "staff_admin": "+79990000000",
    "staff_marketing": "+79990000004",
}


def _client(sheet: MockSheetWrapper, staff_user_id: str = "staff_001") -> TestClient:
    app.dependency_overrides[get_sheet_wrapper] = lambda: sheet
    app.dependency_overrides[get_settings] = make_test_settings
    client = TestClient(app)
    requested = client.post("/auth/request-code", json={"staff_user_id": staff_user_id, "phone": PHONES[staff_user_id]})
    assert requested.status_code == 200
    verified = client.post("/auth/verify-code", json={"staff_user_id": staff_user_id, "code": requested.json()["debug_code"]})
    assert verified.status_code == 200
    return client


def _demo_sheet() -> MockSheetWrapper:
    return MockSheetWrapper(demo_tabs(today=TODAY))


def _booking(client: TestClient, booking_id: str) -> dict:
    listed = client.get(f"/bookings?date={TODAY.isoformat()}")
    assert listed.status_code == 200
    return next(item for item in listed.json() if item["booking_id"] == booking_id)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_new_columns_are_optional_not_required() -> None:
    for column in ("wetsuit_id", "board_id", "drink", "equipment_issued_by", "equipment_issued_at"):
        assert column not in TAB_SCHEMAS["bookings"].required_columns
        assert column in migration_columns("bookings")
    assert "prefs_reset_at" in migration_columns("clients")
    assert "prefs_reset_at" not in TAB_SCHEMAS["clients"].required_columns


def test_last_time_for_returning_client_and_empty_for_first_visit() -> None:
    sheet = _demo_sheet()
    client = _client(sheet)
    returning = _booking(client, "bkg_demo_confirmed")
    last = returning["last_time"]
    assert last["booking_id"] == "bkg_demo_hist_2"
    assert last["wetsuit"]["number"] == "14"
    assert last["wetsuit"]["size"] == "M"
    assert last["wetsuit"]["gender"] == "female"
    assert last["board"]["number"] == "7"
    assert last["drink"] == "chocolate"
    assert last["issued_by_name"] == "Ольга Кузнецова"
    assert returning["visits_before"] == 2

    first = _booking(client, "bkg_demo_ready")
    assert first["last_time"] is None
    assert first["visits_before"] == 0


def test_last_time_needs_no_extra_reads_per_booking() -> None:
    sheet = _demo_sheet()
    reads: list[str] = []
    original = sheet.read_tab
    original_optional = sheet.read_optional_tab

    def counting(tab: str):
        reads.append(tab)
        return original(tab)

    def counting_optional(tab: str):
        reads.append(tab)
        return original_optional(tab)

    sheet.read_tab = counting  # type: ignore[method-assign]
    sheet.read_optional_tab = counting_optional  # type: ignore[method-assign]
    from apps.api.app.services.bookings import list_bookings

    items = list_bookings(sheet, club_id="ice_beach_ruza", target_date=TODAY.isoformat())
    assert len(items) >= 2
    assert reads.count("bookings") == 1
    assert reads.count("boards") == 1
    assert reads.count("wetsuits") == 1


def test_operator_issues_equipment_with_audit_and_conflict_warning() -> None:
    sheet = _demo_sheet()
    client = _client(sheet)
    response = client.patch(
        "/bookings/bkg_demo_ready/equipment",
        json={"wetsuit_id": "wst_demo_08", "board_id": "brd_demo_05", "drink": "coffee"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["warnings"] == []
    booking = body["booking"]
    assert booking["wetsuit"]["number"] == "8"
    assert booking["board"]["number"] == "5"
    assert booking["drink"] == "coffee"
    assert booking["equipment_issued_by"] == "staff_001"
    assert booking["equipment_issued_at"]
    assert any(row.get("action") == "equipment_issued" and row.get("entity_id") == "bkg_demo_ready" for row in sheet.tabs["audit_log"])

    # Тот же гидрокостюм на запись 10:30 — предупреждение, но не блокировка.
    second = client.patch("/bookings/bkg_demo_confirmed/equipment", json={"wetsuit_id": "wst_demo_08"})
    assert second.status_code == 200
    assert any("Гидрокостюм № 8" in warning for warning in second.json()["warnings"])


def test_repeat_last_one_tap_and_first_visit_conflict() -> None:
    sheet = _demo_sheet()
    client = _client(sheet)
    repeated = client.post("/bookings/bkg_demo_confirmed/equipment/repeat-last")
    assert repeated.status_code == 200, repeated.text
    booking = repeated.json()["booking"]
    assert booking["wetsuit_id"] == "wst_demo_14"
    assert booking["board_id"] == "brd_demo_07"
    assert booking["drink"] == "chocolate"
    assert booking["last_time"]["booking_id"] == "bkg_demo_hist_2"
    assert any(row.get("action") == "equipment_repeat_last" for row in sheet.tabs["audit_log"])

    no_history = client.post("/bookings/bkg_demo_ready/equipment/repeat-last")
    assert no_history.status_code == 409


def test_validation_rejects_unknown_inactive_and_bad_drink() -> None:
    sheet = _demo_sheet()
    client = _client(sheet)
    assert client.patch("/bookings/bkg_demo_ready/equipment", json={"board_id": "brd_missing"}).status_code == 422
    assert client.patch("/bookings/bkg_demo_ready/equipment", json={"board_id": "brd_demo_12"}).status_code == 422
    assert client.patch("/bookings/bkg_demo_ready/equipment", json={"drink": "tea"}).status_code == 422
    assert client.patch("/bookings/bkg_demo_ready/equipment", json={}).status_code == 422
    assert client.patch("/bookings/bkg_missing/equipment", json={"drink": "none"}).status_code == 404


def test_pilot_sees_only_board_and_cannot_edit() -> None:
    sheet = _demo_sheet()
    _client(sheet).post("/bookings/bkg_demo_confirmed/equipment/repeat-last")
    pilot = _client(sheet, "staff_pilot")
    item = _booking(pilot, "bkg_demo_confirmed")
    assert item["board"]["number"] == "7"
    assert item["wetsuit"] is None and item["wetsuit_id"] is None
    assert item["drink"] is None
    assert item["last_time"]["board"]["number"] == "7"
    assert item["last_time"]["wetsuit"] is None
    assert item["last_time"]["drink"] is None

    queue = pilot.get(f"/pilot/today?date={TODAY.isoformat()}")
    assert queue.status_code == 200
    queued = next(row for row in queue.json() if row["booking_id"] == "bkg_demo_confirmed")
    assert queued["board"]["number"] == "7"
    assert queued["last_board"]["number"] == "7"
    assert "wetsuit" not in queued and "drink" not in queued

    assert pilot.patch("/bookings/bkg_demo_confirmed/equipment", json={"board_id": "brd_demo_03"}).status_code == 403
    assert pilot.post("/inventory/boards", json={"number": "99", "kind": "wakeboard"}).status_code == 403
    assert pilot.get("/inventory/boards").status_code == 200


def test_marketing_sees_no_equipment() -> None:
    sheet = _demo_sheet()
    _client(sheet).post("/bookings/bkg_demo_confirmed/equipment/repeat-last")
    marketing = _client(sheet, "staff_marketing")
    live = marketing.get(f"/shift/live?date={TODAY.isoformat()}")
    assert live.status_code == 200
    focus = live.json()["focus_booking"]
    if focus:
        assert focus["last_time"] is None
        assert focus["wetsuit"] is None and focus["board"] is None and focus["drink"] is None
    assert marketing.get("/inventory/boards").status_code == 403


def test_coach_changes_board_only_on_own_booking() -> None:
    sheet = _demo_sheet()
    for row in sheet.tabs["bookings"]:
        if row["booking_id"] == "bkg_demo_confirmed":
            row["coach_required"] = "true"
            row["coach_user_id"] = "staff_coach"
    coach = _client(sheet, "staff_coach")
    ok = coach.patch("/bookings/bkg_demo_confirmed/equipment", json={"board_id": "brd_demo_09"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["booking"]["board"]["number"] == "9"
    assert coach.patch("/bookings/bkg_demo_confirmed/equipment", json={"drink": "coffee"}).status_code == 403
    assert coach.patch("/bookings/bkg_demo_ready/equipment", json={"board_id": "brd_demo_09"}).status_code == 403


def test_inventory_crud_admin_only_and_unique_numbers() -> None:
    sheet = _demo_sheet()
    admin = _client(sheet, "staff_admin")
    created = admin.post("/inventory/boards", json={"number": "15", "name": "Ronix One", "kind": "wakeboard", "length_cm": 144})
    assert created.status_code == 200, created.text
    board_id = created.json()["board_id"]
    assert admin.post("/inventory/boards", json={"number": "15", "kind": "surf"}).status_code == 409
    renamed = admin.patch(f"/inventory/boards/{board_id}", json={"name": "Ronix One ATR"})
    assert renamed.json()["name"] == "Ronix One ATR"
    deactivated = admin.patch(f"/inventory/boards/{board_id}", json={"is_active": False})
    assert deactivated.json()["is_active"] is False

    operator = _client(sheet)
    active = operator.get("/inventory/boards").json()
    assert board_id not in {row["board_id"] for row in active}
    assert "brd_demo_12" not in {row["board_id"] for row in active}
    assert operator.post("/inventory/boards", json={"number": "16", "kind": "surf"}).status_code == 403

    admin = _client(sheet, "staff_admin")
    all_rows = admin.get("/inventory/boards?include_inactive=true").json()
    assert board_id in {row["board_id"] for row in all_rows}

    suit = admin.post("/inventory/wetsuits", json={"number": "30", "size": "L", "gender": "female"})
    assert suit.status_code == 200
    assert suit.json()["size"] == "L"
    assert admin.post("/inventory/wetsuits", json={"number": "31", "size": "XXXL", "gender": "female"}).status_code == 422
    assert any(row.get("action") == "inventory_deactivated" for row in sheet.tabs["audit_log"])


def test_admin_prefs_reset_hides_older_history() -> None:
    sheet = _demo_sheet()
    operator = _client(sheet)
    assert operator.post("/clients/client_2/prefs/reset").status_code == 403
    admin = _client(sheet, "staff_admin")
    reset = admin.post("/clients/client_2/prefs/reset")
    assert reset.status_code == 200
    assert reset.json()["prefs_reset_at"]
    item = _booking(admin, "bkg_demo_confirmed")
    assert item["last_time"] is None
    # Прошлые выдачи не стираются.
    history = next(row for row in sheet.tabs["bookings"] if row["booking_id"] == "bkg_demo_hist_2")
    assert history["wetsuit_id"] == "wst_demo_14"


def test_legacy_sheet_keeps_working_and_preflight_warns() -> None:
    sheet = MockSheetWrapper(demo_tabs(today=TODAY), legacy_sheet=True)
    for row in sheet.tabs["bookings"]:
        for column in ("wetsuit_id", "board_id", "drink", "equipment_issued_by", "equipment_issued_at"):
            row.pop(column, None)
    sheet.tabs.pop("boards", None)
    sheet.tabs.pop("wetsuits", None)

    client = _client(sheet)
    item = _booking(client, "bkg_demo_confirmed")
    assert item["last_time"] is None
    assert client.get("/inventory/boards").json() == []
    blocked = client.patch("/bookings/bkg_demo_ready/equipment", json={"drink": "coffee"})
    assert blocked.status_code == 409
    assert "python -m packages.sheets" in blocked.json()["detail"]
    admin = _client(sheet, "staff_admin")
    assert admin.post("/inventory/boards", json={"number": "1", "kind": "wakeboard"}).status_code == 409

    summary = run_preflight_check(sheet, target_date=TODAY.isoformat())
    assert summary["blockers"] == 0
    codes = {item["code"]: item["level"] for item in summary["checks"]}
    assert codes["tab:boards"] == "WARN"
    assert codes["tab:wetsuits"] == "WARN"
    assert codes["columns:bookings"] == "WARN"


def test_preflight_passes_on_migrated_demo() -> None:
    summary = run_preflight_check(_demo_sheet(), target_date=TODAY.isoformat())
    codes = {item["code"]: item["level"] for item in summary["checks"]}
    assert codes["tab:boards"] == "PASS"
    assert codes["columns:bookings"] == "PASS"
