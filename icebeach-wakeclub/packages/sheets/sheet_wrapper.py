"""Google Sheets wrapper with schema validation and audit logging."""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .schema import validate_required_columns

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


def _truthy_env(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y"}


class SheetWrapper:
    def __init__(
        self,
        spreadsheet_id: str,
        service_account_json_path: str | None = None,
        service_account_info: dict[str, Any] | None = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id

        if service_account_info is not None:
            creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        elif service_account_json_path:
            creds = Credentials.from_service_account_file(service_account_json_path, scopes=SCOPES)
        else:
            raise ValueError("Google service account credentials are required")

        self._creds = creds
        self._disable_proxy = _truthy_env("DISABLE_SYSTEM_PROXY_FOR_GOOGLE", "true")
        self._tab_cache_ttl_seconds = int(os.getenv("SHEETS_TAB_CACHE_TTL_SECONDS", "15"))
        self._tab_cache: dict[str, tuple[float, list[list[str]]]] = {}
        self.service = self._build_service()

    def _build_http(self) -> AuthorizedHttp:
        base_http = httplib2.Http(timeout=20, proxy_info=None) if self._disable_proxy else httplib2.Http(timeout=20)
        return AuthorizedHttp(self._creds, http=base_http)

    def _build_service(self):
        return build("sheets", "v4", http=self._build_http(), cache_discovery=False)

    def _refresh_service(self) -> None:
        self.service = self._build_service()

    def _execute_with_retries(self, request_factory, *, attempts: int = 4, base_sleep_seconds: float = 0.6):
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                request = request_factory()
                return request.execute()
            except (ssl.SSLError, OSError) as exc:
                last_exc = exc
                self._refresh_service()
                if i == attempts - 1:
                    raise
                time.sleep(base_sleep_seconds * (2**i))
        if last_exc:
            raise last_exc

    def read_tab(self, tab_name: str) -> list[dict[str, str]]:
        values = self._fetch_values(tab_name)
        if not values:
            return []

        headers = values[0]
        validate_required_columns(tab_name, headers)
        body = values[1:]

        rows: list[dict[str, str]] = []
        for row in body:
            normalized = row + [""] * (len(headers) - len(row))
            rows.append(dict(zip(headers, normalized, strict=False)))
        return rows

    def append_row(self, tab_name: str, row: dict[str, Any], *, unique_key: str | None = None) -> None:
        values = self._fetch_values(tab_name)
        if not values:
            raise ValueError(f"Tab '{tab_name}' is empty or missing header row")

        headers = values[0]
        validate_required_columns(tab_name, headers)

        if unique_key and unique_key not in headers:
            raise ValueError(f"Unique key column '{unique_key}' is missing in '{tab_name}'")

        unique_value = self._serialize_cell(row.get(unique_key, "")) if unique_key else None
        if unique_key and unique_value and self.find(tab_name, {unique_key: unique_value}):
            return

        row_values = [self._serialize_cell(row.get(col, "")) for col in headers]

        try:
            self._execute_with_retries(
                lambda: self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{tab_name}!A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row_values]},
                )
            )
        except (ssl.SSLError, OSError):
            self._tab_cache.pop(tab_name, None)
            if unique_key and unique_value and self.find(tab_name, {unique_key: unique_value}):
                return
            raise

        self._tab_cache.pop(tab_name, None)
        if unique_key and unique_value:
            matches = self.find(tab_name, {unique_key: unique_value})
            if len(matches) > 1:
                raise ValueError(f"Duplicate rows detected in '{tab_name}' for {unique_key}={unique_value}")

    def find(self, tab_name: str, filters: dict[str, Any]) -> list[dict[str, str]]:
        rows = self.read_tab(tab_name)
        result: list[dict[str, str]] = []
        for row in rows:
            if all(str(row.get(k, "")) == str(v) for k, v in filters.items()):
                result.append(row)
        return result

    def update_by_id(
        self,
        tab_name: str,
        id_column: str,
        id_value: str,
        patch: dict[str, Any],
        *,
        actor: str = "system",
        audit_entity: str | None = None,
    ) -> dict[str, str]:
        values = self._fetch_values(tab_name)
        if not values:
            raise ValueError(f"Tab '{tab_name}' is empty or missing header row")

        headers = values[0]
        validate_required_columns(tab_name, headers)

        if id_column not in headers:
            raise ValueError(f"ID column '{id_column}' is missing in '{tab_name}'")

        matches: list[tuple[int, dict[str, str]]] = []
        id_idx = headers.index(id_column)
        for i, row in enumerate(values[1:], start=2):
            normalized = row + [""] * (len(headers) - len(row))
            if normalized[id_idx] == id_value:
                matches.append((i, dict(zip(headers, normalized, strict=False))))

        if not matches:
            raise ValueError(f"Row not found in '{tab_name}' where {id_column}={id_value}")
        if len(matches) > 1:
            raise ValueError(f"Duplicate rows found in '{tab_name}' where {id_column}={id_value}")

        row_idx, old_row = matches[0]
        new_row = dict(old_row)
        for key, val in patch.items():
            if key in headers:
                new_row[key] = self._serialize_cell(val)

        row_values = [new_row.get(col, "") for col in headers]
        end_col = self._column_letter(len(headers))
        self._execute_with_retries(
            lambda: self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!A{row_idx}:{end_col}{row_idx}",
                valueInputOption="RAW",
                body={"values": [row_values]},
            )
        )
        self._tab_cache.pop(tab_name, None)

        diff = {k: {"old": old_row.get(k, ""), "new": new_row.get(k, "")} for k in patch if k in headers}
        self.write_audit(
            action="update",
            entity=audit_entity or tab_name.rstrip("s"),
            entity_id=id_value,
            diff_json=diff,
            actor=actor,
        )

        return new_row

    def update_matching(
        self,
        tab_name: str,
        filters: dict[str, Any],
        patch: dict[str, Any],
        *,
        actor: str = "system",
        audit_entity: str | None = None,
    ) -> dict[str, str]:
        values = self._fetch_values(tab_name)
        if not values:
            raise ValueError(f"Tab '{tab_name}' is empty or missing header row")

        headers = values[0]
        validate_required_columns(tab_name, headers)

        matches: list[tuple[int, dict[str, str]]] = []
        for i, row in enumerate(values[1:], start=2):
            normalized = row + [""] * (len(headers) - len(row))
            mapped = dict(zip(headers, normalized, strict=False))
            if all(str(mapped.get(key, "")) == str(value) for key, value in filters.items()):
                matches.append((i, mapped))

        if not matches:
            raise ValueError(f"Row not found in '{tab_name}' matching {filters}")
        if len(matches) > 1:
            raise ValueError(f"Duplicate rows found in '{tab_name}' matching {filters}")

        row_idx, old_row = matches[0]
        new_row = dict(old_row)
        for key, val in patch.items():
            if key in headers:
                new_row[key] = self._serialize_cell(val)

        row_values = [new_row.get(col, "") for col in headers]
        end_col = self._column_letter(len(headers))
        self._execute_with_retries(
            lambda: self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!A{row_idx}:{end_col}{row_idx}",
                valueInputOption="RAW",
                body={"values": [row_values]},
            )
        )
        self._tab_cache.pop(tab_name, None)

        diff = {k: {"old": old_row.get(k, ""), "new": new_row.get(k, "")} for k in patch if k in headers}
        entity_id = str(next(iter(filters.values()), ""))
        self.write_audit(
            action="update",
            entity=audit_entity or tab_name.rstrip("s"),
            entity_id=entity_id,
            diff_json=diff,
            actor=actor,
        )
        return new_row

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
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "diff_json": json.dumps(diff_json, ensure_ascii=False),
        }
        try:
            self.append_row("audit_log", payload)
        except Exception as exc:
            print(
                f"AUDIT_WRITE_FAILED action={action} entity={entity} entity_id={entity_id}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            if strict:
                raise

    def _fetch_values(self, tab_name: str) -> list[list[str]]:
        cached = self._tab_cache.get(tab_name)
        if cached is not None:
            fetched_at, cached_values = cached
            if self._tab_cache_ttl_seconds <= 0 or (time.time() - fetched_at) < self._tab_cache_ttl_seconds:
                return cached_values
            self._tab_cache.pop(tab_name, None)

        response = self._execute_with_retries(
            lambda: self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!A1:ZZ",
            )
        )
        values = response.get("values", [])
        self._tab_cache[tab_name] = (time.time(), values)
        return values

    @staticmethod
    def _serialize_cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _column_letter(column_number: int) -> str:
        result = []
        while column_number > 0:
            column_number, rem = divmod(column_number - 1, 26)
            result.append(chr(65 + rem))
        return "".join(reversed(result))