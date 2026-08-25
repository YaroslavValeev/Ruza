"""In-memory Sheets stand-in for contract tests and local demo (no Google API)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .schema import TAB_SCHEMAS


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
                "consent_face": "false",
                "consent_voice": "false",
                "created_at": "2026-03-01T00:00:00Z",
            },
            {
                "client_id": "client_2",
                "club_id": CLUB_ID,
                "full_name": "Ирина Смирнова",
                "phone": "+79990000012",
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


def demo_tabs(*, today: date | None = None) -> dict[str, list[dict[str, str]]]:
    """Richer seed so the dashboard can be exercised without Google Sheets."""
    tabs = default_minimal_tabs()
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
            "wetsuit_required": "true",
            "wetsuit_size": "M",
            "wetsuit_gender": "male",
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
            "wetsuit_required": "false",
            "wetsuit_size": "",
            "wetsuit_gender": "",
            "notes": "",
            "discount": "0",
        },
    ]
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
    def __init__(self, tabs: dict[str, list[dict[str, str]]] | None = None) -> None:
        self.tabs: dict[str, list[dict[str, str]]] = tabs or default_minimal_tabs()

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
