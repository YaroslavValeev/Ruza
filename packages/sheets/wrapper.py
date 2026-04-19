"""Google Sheets wrapper for MVP operations."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


class SheetsConfigError(RuntimeError):
    """Raised when Sheets configuration is invalid."""


class SheetsSchemaError(RuntimeError):
    """Raised when a tab/column contract is broken."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class SheetsConfig:
    spreadsheet_id: str
    service_account_json: str
    cache_ttl_seconds: int = 30

    @classmethod
    def from_env(cls) -> "SheetsConfig":
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        cache_ttl_seconds = int(os.environ.get("SHEETS_CACHE_TTL_SECONDS", "30").strip())
        if not spreadsheet_id:
            raise SheetsConfigError("SPREADSHEET_ID is required")
        if not service_account_json:
            raise SheetsConfigError("GOOGLE_SERVICE_ACCOUNT_JSON is required")
        if not os.path.exists(service_account_json):
            raise SheetsConfigError(
                f"Service account JSON was not found: {service_account_json}"
            )
        return cls(
            spreadsheet_id=spreadsheet_id,
            service_account_json=service_account_json,
            cache_ttl_seconds=cache_ttl_seconds,
        )


class SheetWrapper:
    """Thin wrapper over Google Sheets API for table-like operations."""

    REFERENCE_TABS = {"staff_users", "boats", "pricing"}

    def __init__(self, config: SheetsConfig):
        self.config = config
        self._service = None
        self._cache: dict[str, tuple[float, list]] = {}

    def _service_client(self):
        if self._service is None:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(
                self.config.service_account_json,
                scopes=scopes,
            )
            self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def _read_values(self, tab: str):
        now = time.time()
        cached = self._cache.get(tab)
        if cached and cached[0] > now:
            return cached[1]

        try:
            values = (
                self._service_client()
                .spreadsheets()
                .values()
                .get(spreadsheetId=self.config.spreadsheet_id, range=f"{tab}!A:ZZ")
                .execute()
                .get("values", [])
            )
        except Exception as exc:
            raise SheetsSchemaError("TAB_MISSING", f"Tab '{tab}' not found or inaccessible") from exc

        if tab in self.REFERENCE_TABS:
            self._cache[tab] = (now + self.config.cache_ttl_seconds, values)
        return values

    def _invalidate_cache(self, tab: str) -> None:
        self._cache.pop(tab, None)

    def read_tab(self, tab: str) -> list[dict]:
        values = self._read_values(tab)
        if not values:
            return []
        headers = values[0]
        rows = []
        for raw_row in values[1:]:
            row = {h: raw_row[i] if i < len(raw_row) else "" for i, h in enumerate(headers)}
            rows.append(row)
        return rows

    def append_row(self, tab: str, row: dict) -> None:
        values = self._read_values(tab)
        if not values:
            raise SheetsSchemaError("TAB_MISSING", f"Tab '{tab}' has no header row")
        headers = values[0]
        values_to_append = [row.get(header, "") for header in headers]
        (
            self._service_client()
            .spreadsheets()
            .values()
            .append(
                spreadsheetId=self.config.spreadsheet_id,
                range=f"{tab}!A:ZZ",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [values_to_append]},
            )
            .execute()
        )
        self._invalidate_cache(tab)

    def find(self, tab: str, predicate: Callable[[dict], bool]) -> list[dict]:
        return [row for row in self.read_tab(tab) if predicate(row)]

    def update_by_id(self, tab: str, id_field: str, id_value: str, patch: dict) -> bool:
        values = self._read_values(tab)
        if not values:
            return False
        headers = values[0]
        try:
            id_index = headers.index(id_field)
        except ValueError:
            raise SheetsSchemaError(
                "COLUMN_MISSING", f"Column '{id_field}' missing in '{tab}'"
            )

        for idx, raw_row in enumerate(values[1:], start=2):
            current_id = raw_row[id_index] if id_index < len(raw_row) else ""
            if current_id == id_value:
                row_values = [raw_row[i] if i < len(raw_row) else "" for i in range(len(headers))]
                for key, value in patch.items():
                    if key in headers:
                        row_values[headers.index(key)] = value
                (
                    self._service_client()
                    .spreadsheets()
                    .values()
                    .update(
                        spreadsheetId=self.config.spreadsheet_id,
                        range=f"{tab}!A{idx}:ZZ{idx}",
                        valueInputOption="RAW",
                        body={"values": [row_values]},
                    )
                    .execute()
                )
                self._invalidate_cache(tab)
                return True
        return False

    def validate_required_columns(self, tab: str, required_columns: list[str]) -> list[str]:
        values = self._read_values(tab)
        if not values:
            return required_columns
        headers = set(values[0])
        return [column for column in required_columns if column not in headers]

    def write_audit(
        self,
        action: str,
        entity: str,
        entity_id: str,
        diff_json: dict,
        actor: str = "system",
    ) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": actor,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "diff_json": json.dumps(diff_json, ensure_ascii=False),
        }
        self.append_row("audit_log", payload)
