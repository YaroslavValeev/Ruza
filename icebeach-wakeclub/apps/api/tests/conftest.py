from __future__ import annotations

import sys
from pathlib import Path

from apps.api.app.config import Settings


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class MockSheetWrapper:
    def __init__(self) -> None:
        self.tabs: dict[str, list[dict[str, str]]] = {
            "staff_users": [
                {
                    "staff_user_id": "staff_001",
                    "club_id": "ice_beach_ruza",
                    "role": "operator",
                    "full_name": "Operator One",
                    "phone": "+79990000001",
                    "telegram_id": "",
                    "is_active": "true",
                    "created_at": "2026-03-01T00:00:00Z",
                },
                {
                    "staff_user_id": "staff_pilot",
                    "club_id": "ice_beach_ruza",
                    "role": "pilot",
                    "full_name": "Pilot One",
                    "phone": "+79990000002",
                    "telegram_id": "",
                    "is_active": "true",
                    "created_at": "2026-03-01T00:00:00Z",
                },
                {
                    "staff_user_id": "staff_coach",
                    "club_id": "ice_beach_ruza",
                    "role": "coach",
                    "full_name": "Coach One",
                    "phone": "+79990000003",
                    "telegram_id": "",
                    "is_active": "true",
                    "created_at": "2026-03-01T00:00:00Z",
                },
            ],
            "boats": [
                {
                    "boat_id": "boat_1",
                    "club_id": "ice_beach_ruza",
                    "boat_name": "Axis A",
                    "capacity_default": "1",
                    "pilot_user_id": "staff_pilot",
                    "is_active": "true",
                }
            ],
            "clients": [
                {
                    "client_id": "client_1",
                    "club_id": "ice_beach_ruza",
                    "full_name": "Client One",
                    "phone": "+79990000011",
                    "consent_face": "false",
                    "consent_voice": "false",
                    "created_at": "2026-03-01T00:00:00Z",
                }
            ],
            "pricing": [
                {
                    "price_id": "price_1",
                    "club_id": "ice_beach_ruza",
                    "valid_from": "2026-01-01",
                    "base_price": "12000",
                    "coach_price": "3500",
                    "currency": "RUB",
                }
            ],
            "schedule": [
                {
                    "schedule_id": "sch_1",
                    "club_id": "ice_beach_ruza",
                    "weekday": "0",
                    "time": "10:00",
                    "boat_id": "boat_1",
                    "capacity": "1",
                    "is_active": "true",
                    "notes": "",
                }
            ],
            "slot_overrides": [],
            "bookings": [],
            "checkins": [],
            "analytics_daily": [],
            "kpi_targets": [],
            "leads": [],
            "campaigns": [],
            "utm_events": [],
            "auth_codes": [],
            "audit_log": [],
        }

    def read_tab(self, tab_name: str) -> list[dict[str, str]]:
        return list(self.tabs.get(tab_name, []))

    def append_row(self, tab_name: str, row: dict[str, str], *, unique_key: str | None = None) -> None:
        serialized = {k: str(v) for k, v in row.items()}
        if unique_key is not None:
            for existing in self.tabs.setdefault(tab_name, []):
                if str(existing.get(unique_key, "")) == str(serialized.get(unique_key, "")):
                    return
        self.tabs.setdefault(tab_name, []).append(serialized)

    def find(self, tab_name: str, filters: dict[str, str]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for row in self.tabs.get(tab_name, []):
            if all(str(row.get(k, "")) == str(v) for k, v in filters.items()):
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
                    updated[key] = str(value)
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

    def write_audit(self, action: str, entity: str, entity_id: str, diff_json: dict, *, actor: str = "system") -> None:
        self.tabs["audit_log"].append(
            {
                "ts": "2026-06-01T00:00:00Z",
                "actor": actor,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "diff_json": str(diff_json),
            }
        )


def make_test_settings() -> Settings:
    return Settings(
        spreadsheet_id="test-sheet",
        service_account_json_path=str(Path(__file__).resolve()),
        service_account_info=None,
        session_secret="test-secret",
        session_max_age_seconds=3600,
        session_cookie_name="icebeach_session",
        session_cookie_secure=False,
        allow_legacy_staff_login=False,
        auth_code_ttl_seconds=300,
        auth_code_rate_limit_window_seconds=600,
        auth_code_rate_limit_max_attempts=5,
        debug_auth_codes_in_response=True,
        cors_allow_origins=(),
        cors_allow_origin_regex=None,
        api_host="127.0.0.1",
        api_port=8000,
        environment="test",
    )
