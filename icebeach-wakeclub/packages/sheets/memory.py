"""In-memory Sheets stand-in for contract tests and local demo (no Google API)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .schema import OPTIONAL_COLUMNS, OPTIONAL_TABS, TAB_SCHEMAS, migration_columns


CLUB_ID = "ice_beach_ruza"


def _staff(
    staff_user_id: str,
    role: str,
    full_name: str,
    phone: str,
) -> dict[str, str]:
    return {
        "staff_user_id": staff_user_id,
        "club_id": CLUB_ID,
        "role": role,
        "full_name": full_name,
        "phone": phone,
        "telegram_id": "",
        "is_active": "true",
        "created_at": "2026-03-01T00:00:00Z",
    }


def default_minimal_tabs() -> dict[str, list[dict[str, str]]]:
    """Seed used by contract tests: one Monday 10:00 slot, operator + pilot + coach."""
    return {
        "staff_users": [
            _staff("staff_001", "operator", "Operator One", "+79990000001"),
            _staff("staff_pilot", "pilot", "Pilot One", "+79990000002"),
            _staff("staff_coach", "coach", "Coach One", "+79990000003"),
            _staff("staff_admin", "admin", "Admin One", "+79990000000"),
            _staff("staff_marketing", "marketing_read", "Marketing One", "+79990000004"),
        ],
        "boats": [
            {
                "boat_id": "boat_1",
                "club_id": CLUB_ID,
                "boat_name": "Axis A",
                "capacity_default": "1",
                "pilot_user_id": "staff_pilot",
                "is_active": "true",
            }
        ],
        "clients": [
            {
                "client_id": "client_1",
                "club_id": CLUB_ID,
                "full_name": "Client One",
                "phone": "+79990000011",
                "telegram_id": "",
                "consent_face": "false",
                "consent_voice": "false",
                "created_at": "2026-03-01T00:00:00Z",
            },
            {
                "client_id": "client_2",
                "club_id": CLUB_ID,
                "full_name": "Ирина Смирнова",
                "phone": "+79990000012",
                "telegram_id": "",
                "consent_face": "true",
                "consent_voice": "true",
                "created_at": "2026-03-01T00:00:00Z",
            },
        ],
        "pricing": [
            {
                "price_id": "price_1",
                "club_id": CLUB_ID,
                "valid_from": "2026-01-01",
                "base_price": "12000",
                "coach_price": "3500",
                "currency": "RUB",
            }
        ],
        "schedule": [
            {
                "schedule_id": "sch_1",
                "club_id": CLUB_ID,
                "weekday": "0",
                "time": "07:00",
                "boat_id": "boat_1",
                "capacity": "1",
                "is_active": "true",
                "notes": "",
            }
        ],
        "slot_overrides": [],
        "bookings": [],
        "payments": [],
        "payment_closures": [],
        "checkins": [],
        "analytics_daily": [],
        "kpi_targets": [],
        "leads": [],
        "campaigns": [],
        "utm_events": [],
        "auth_codes": [],
        "audit_log": [],
        "clubs": [
            {
                "club_id": CLUB_ID,
                "club_name": "Ice Beach Ruza",
                "timezone": "Europe/Moscow",
                "is_active": "true",
            }
        ],
    }


# Русские имена только для демо-стенда (demo_tabs). Контрактные тесты используют
# default_minimal_tabs() с прежними именами, реальные данные не затрагиваются.
DEMO_STAFF_NAMES_RU = {
    "staff_admin": "Андрей Лебедев",
    "staff_001": "Ольга Кузнецова",
    "staff_pilot": "Дмитрий Соколов",
    "staff_coach": "Сергей Морозов",
    "staff_marketing": "Мария Новикова",
}
DEMO_CLIENT_NAMES_RU = {
    "client_1": "Алексей Иванов",
}


def _apply_demo_names_ru(tabs: dict[str, list[dict[str, str]]]) -> None:
    for row in tabs.get("staff_users", []):
        row["full_name"] = DEMO_STAFF_NAMES_RU.get(row.get("staff_user_id", ""), row.get("full_name", ""))
    for row in tabs.get("clients", []):
        row["full_name"] = DEMO_CLIENT_NAMES_RU.get(row.get("client_id", ""), row.get("full_name", ""))


def _demo_board(board_id: str, number: str, name: str, kind: str, length_cm: str, *, active: bool = True) -> dict[str, str]:
    return {
        "board_id": board_id,
        "club_id": CLUB_ID,
        "number": number,
        "name": name,
        "kind": kind,
        "length_cm": length_cm,
        "is_active": "true" if active else "false",
        "created_at": "2026-05-01T09:00:00Z",
        "updated_at": "2026-05-01T09:00:00Z",
    }


def _demo_wetsuit(wetsuit_id: str, number: str, size: str, gender: str, *, active: bool = True) -> dict[str, str]:
    return {
        "wetsuit_id": wetsuit_id,
        "club_id": CLUB_ID,
        "number": number,
        "size": size,
        "gender": gender,
        "is_active": "true" if active else "false",
        "created_at": "2026-05-01T09:00:00Z",
        "updated_at": "2026-05-01T09:00:00Z",
    }


def _demo_past_booking(
    booking_id: str,
    client_id: str,
    day: date,
    time_text: str,
    ride_type: str,
    *,
    wetsuit_id: str = "",
    board_id: str = "",
    drink: str = "",
    issued_by: str = "staff_001",
) -> dict[str, str]:
    """Прошлый завершённый заезд с выданным снаряжением — история для «Как в прошлый раз»."""
    stamp = f"{day.isoformat()}T{time_text}:00Z"
    return {
        "booking_id": booking_id,
        "club_id": CLUB_ID,
        "client_id": client_id,
        "date": day.isoformat(),
        "time": time_text,
        "boat_id": "boat_1",
        "status": "done",
        "total_price": "12000",
        "created_by": "staff_001",
        "created_at": stamp,
        "updated_at": stamp,
        "coach_required": "false",
        "coach_user_id": "",
        "ride_type": ride_type,
        "sets_count": "1",
        "wetsuit_required": "true" if wetsuit_id else "false",
        "wetsuit_size": "",
        "wetsuit_gender": "",
        "warmup_state": "warmed_up",
        "timer_state": "completed",
        "timer_started_at": "",
        "timer_anchor_at": "",
        "elapsed_seconds": "1500",
        "actual_duration_seconds": "1500",
        "admin_notice_15_sent_at": "",
        "admin_notice_5_sent_at": "",
        "client_notice_15_sent_at": "",
        "client_notice_5_sent_at": "",
        "next_client_notified_at": "",
        "notes": "",
        "discount": "0",
        "wetsuit_id": wetsuit_id,
        "board_id": board_id,
        "drink": drink,
        "equipment_issued_by": issued_by if (wetsuit_id or board_id or drink) else "",
        "equipment_issued_at": stamp if (wetsuit_id or board_id or drink) else "",
    }


def _apply_demo_equipment(tabs: dict[str, list[dict[str, str]]], today: date) -> None:
    """Справочник инвентаря и постоянная клиентка с историей (Ирина Смирнова, 3-й визит)."""
    tabs["boards"] = [
        _demo_board("brd_demo_03", "3", "Hyperlite Murray", "wakeboard", "140"),
        _demo_board("brd_demo_05", "5", "Liquid Force Trip", "wakeboard", "138"),
        _demo_board("brd_demo_07", "7", "Ronix Koal Classic", "surf", "142"),
        _demo_board("brd_demo_09", "9", "Slingshot Nomad", "wakeboard", "146"),
        _demo_board("brd_demo_11", "11", "Hyperlite Shim", "skim", "132"),
        _demo_board("brd_demo_12", "12", "Liquid Force Remedy", "wakeboard", "134", active=False),
    ]
    tabs["wetsuits"] = [
        _demo_wetsuit("wst_demo_03", "3", "S", "female"),
        _demo_wetsuit("wst_demo_08", "8", "M", "male"),
        _demo_wetsuit("wst_demo_12", "12", "L", "male"),
        _demo_wetsuit("wst_demo_14", "14", "M", "female"),
        _demo_wetsuit("wst_demo_18", "18", "XL", "male"),
        _demo_wetsuit("wst_demo_21", "21", "XS", "female", active=False),
    ]
    tabs.setdefault("bookings", []).extend(
        [
            _demo_past_booking(
                "bkg_demo_hist_1", "client_2", today - timedelta(days=23), "11:00", "surf",
                wetsuit_id="wst_demo_03", board_id="brd_demo_07", drink="coffee",
            ),
            _demo_past_booking(
                "bkg_demo_hist_2", "client_2", today - timedelta(days=9), "12:30", "surf",
                wetsuit_id="wst_demo_14", board_id="brd_demo_07", drink="chocolate",
            ),
        ]
    )


def demo_tabs(*, today: date | None = None) -> dict[str, list[dict[str, str]]]:
    """Richer seed so the dashboard can be exercised without Google Sheets."""
    tabs = default_minimal_tabs()
    _apply_demo_names_ru(tabs)
    today = today or date.today()
    schedule: list[dict[str, str]] = []
    for day in range(7):
        schedule.append(
            {
                "schedule_id": f"sch_{day}",
                "club_id": CLUB_ID,
                "weekday": str(day),
                "time": "07:00",
                "boat_id": "boat_1",
                "capacity": "1",
                "is_active": "true",
                "notes": "",
            }
        )
    tabs["schedule"] = schedule
    tabs["leads"] = [
        {
            "lead_id": "lead_demo_1",
            "club_id": CLUB_ID,
            "full_name": "Анна Волкова",
            "phone": "79990000021",
            "source": "instagram",
            "status": "new",
            "utm_source": "ig",
            "utm_campaign": "summer",
            "created_at": f"{today.isoformat()}T08:00:00Z",
            "external_source": "demo",
            "external_record_id": "demo-lead-1",
            "received_at": f"{today.isoformat()}T08:00:00Z",
            "sync_status": "demo",
            "sync_error": "",
            "converted_booking_id": "",
            "notes": "Хочет пробный заезд",
        },
        {
            "lead_id": "lead_demo_2",
            "club_id": CLUB_ID,
            "full_name": "Павел Орлов",
            "phone": "79990000022",
            "source": "offline",
            "status": "booked",
            "utm_source": "",
            "utm_campaign": "",
            "created_at": f"{(today - timedelta(days=3)).isoformat()}T10:00:00Z",
            "external_source": "demo",
            "external_record_id": "demo-lead-2",
            "received_at": f"{(today - timedelta(days=3)).isoformat()}T10:00:00Z",
            "sync_status": "demo",
            "sync_error": "",
            "converted_booking_id": "",
            "notes": "",
        },
    ]
    tabs["bookings"] = [
        {
            "booking_id": "bkg_demo_ready",
            "club_id": CLUB_ID,
            "client_id": "client_1",
            "date": today.isoformat(),
            "time": "10:00",
            "boat_id": "boat_1",
            "status": "ready",
            "total_price": "12000",
            "created_by": "staff_001",
            "created_at": f"{today.isoformat()}T07:00:00Z",
            "updated_at": f"{today.isoformat()}T07:10:00Z",
            "coach_required": "false",
            "coach_user_id": "",
            "ride_type": "wakeboard",
            "sets_count": "1",
            "wetsuit_required": "true",
            "wetsuit_size": "M",
            "wetsuit_gender": "male",
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
            "notes": "Гидрокостюм к старту",
            "discount": "0",
        },
        {
            "booking_id": "bkg_demo_confirmed",
            "club_id": CLUB_ID,
            "client_id": "client_2",
            "date": today.isoformat(),
            "time": "10:30",
            "boat_id": "boat_1",
            "status": "confirmed",
            "total_price": "12000",
            "created_by": "staff_001",
            "created_at": f"{today.isoformat()}T07:05:00Z",
            "updated_at": f"{today.isoformat()}T07:05:00Z",
            "coach_required": "false",
            "coach_user_id": "",
            "ride_type": "surf",
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
            "discount": "0",
        },
    ]
    _apply_demo_equipment(tabs, today)
    tabs["kpi_targets"] = [
        {
            "target_id": "tgt_day",
            "club_id": CLUB_ID,
            "period": today.strftime("%Y-W%W"),
            "sessions_target": "20",
            "utilization_target_pct": "70",
            "revenue_target": "200000",
        }
    ]
    return tabs


class InMemorySheetWrapper:
    def __init__(self, tabs: dict[str, list[dict[str, str]]] | None = None, *, legacy_sheet: bool = False) -> None:
        self.tabs: dict[str, list[dict[str, str]]] = tabs or default_minimal_tabs()
        # legacy_sheet=True имитирует Таблицу до миграции: нет вкладок инвентаря
        # и необязательных колонок (для тестов и проверки preflight).
        self.legacy_sheet = legacy_sheet

    def read_optional_tab(self, tab_name: str) -> list[dict[str, str]]:
        if self.legacy_sheet and tab_name in OPTIONAL_TABS:
            return []
        return [dict(row) for row in self.tabs.get(tab_name, [])]

    def get_headers(self, tab_name: str) -> list[str] | None:
        if self.legacy_sheet:
            if tab_name in OPTIONAL_TABS or tab_name not in self.tabs:
                return None
            schema = TAB_SCHEMAS.get(tab_name)
            headers = list(schema.required_columns) if schema else []
            for row in self.tabs[tab_name]:
                for key in row:
                    if key not in headers and key not in OPTIONAL_COLUMNS.get(tab_name, ()):
                        headers.append(key)
            return headers or None
        if tab_name not in self.tabs and tab_name not in TAB_SCHEMAS:
            return None
        headers = list(migration_columns(tab_name))
        for row in self.tabs.get(tab_name, []):
            for key in row:
                if key not in headers:
                    headers.append(key)
        return headers or None

    def _fetch_values(self, tab_name: str) -> list[list[str]]:
        if tab_name not in self.tabs:
            raise ValueError(f"Tab '{tab_name}' is empty or missing header row")
        rows = self.tabs[tab_name]
        schema = TAB_SCHEMAS.get(tab_name)
        headers: list[str] = list(schema.required_columns) if schema else []
        for row in rows:
            for key in row:
                if key not in headers:
                    headers.append(key)
        if not headers:
            raise ValueError(f"Tab '{tab_name}' is empty or missing header row")
        values: list[list[str]] = [headers]
        for row in rows:
            values.append([str(row.get(header, "")) for header in headers])
        return values

    def read_tab(self, tab_name: str) -> list[dict[str, str]]:
        return list(self.tabs.get(tab_name, []))

    def append_row(self, tab_name: str, row: dict[str, str], *, unique_key: str | None = None) -> None:
        serialized = {key: "" if value is None else str(value) for key, value in row.items()}
        if unique_key is not None:
            for existing in self.tabs.setdefault(tab_name, []):
                if str(existing.get(unique_key, "")) == str(serialized.get(unique_key, "")):
                    return
        self.tabs.setdefault(tab_name, []).append(serialized)

    def find(self, tab_name: str, filters: dict[str, str]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for row in self.tabs.get(tab_name, []):
            if all(str(row.get(key, "")) == str(value) for key, value in filters.items()):
                result.append(row)
        return result

    def update_by_id(
        self,
        tab_name: str,
        id_column: str,
        id_value: str,
        patch: dict[str, str],
        *,
        actor: str = "system",
        audit_entity: str | None = None,
    ) -> dict[str, str]:
        for index, row in enumerate(self.tabs.get(tab_name, [])):
            if row.get(id_column) == id_value:
                updated = dict(row)
                for key, value in patch.items():
                    updated[key] = "" if value is None else str(value)
                self.tabs[tab_name][index] = updated
                self.write_audit(
                    action="update",
                    entity=audit_entity or tab_name.rstrip("s"),
                    entity_id=id_value,
                    diff_json=patch,
                    actor=actor,
                )
                return updated
        raise ValueError(f"Row not found in '{tab_name}' where {id_column}={id_value}")

    def update_matching(
        self,
        tab_name: str,
        filters: dict[str, str],
        patch: dict[str, str],
        *,
        actor: str = "system",
        audit_entity: str | None = None,
    ) -> dict[str, str]:
        matches: list[int] = []
        for index, row in enumerate(self.tabs.get(tab_name, [])):
            if all(str(row.get(key, "")) == str(value) for key, value in filters.items()):
                matches.append(index)
        if not matches:
            raise ValueError(f"Row not found in '{tab_name}' matching {filters}")
        if len(matches) > 1:
            raise ValueError(f"Duplicate rows found in '{tab_name}' matching {filters}")
        index = matches[0]
        updated = dict(self.tabs[tab_name][index])
        for key, value in patch.items():
            updated[key] = "" if value is None else str(value)
        self.tabs[tab_name][index] = updated
        entity_id = str(next(iter(filters.values()), ""))
        self.write_audit(
            action="update",
            entity=audit_entity or tab_name.rstrip("s"),
            entity_id=entity_id,
            diff_json=patch,
            actor=actor,
        )
        return updated

    def write_audit(
        self,
        action: str,
        entity: str,
        entity_id: str,
        diff_json: dict[str, Any],
        *,
        actor: str = "system",
        strict: bool = False,
    ) -> None:
        self.tabs.setdefault("audit_log", []).append(
            {
                "ts": "2026-06-01T00:00:00Z",
                "actor": actor,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "diff_json": str(diff_json),
            }
        )
