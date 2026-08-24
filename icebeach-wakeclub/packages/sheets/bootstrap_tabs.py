"""Create missing Google Sheets tabs with header rows (checkins, kpi_targets, …)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .schema import TAB_SCHEMAS
from .sheet_wrapper import SheetWrapper

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_REPO_ROOT / ".env.docker")

# Operational tabs that may be introduced after the base workbook was created.
BOOTSTRAP_TABS = ("checkins", "kpi_targets", "leads")

KPI_SEED_ROW = {
    "target_id": "tgt-2026-season",
    "club_id": "ice_beach_ruza",
    "period": "2026-06",
    "sessions_target": "120",
    "utilization_target_pct": "75",
    "revenue_target": "500000",
}


def _resolve_credentials() -> tuple[str, str | None, dict[str, Any] | None]:
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "").strip()
    if not spreadsheet_id:
        raise SystemExit("SPREADSHEET_ID is not set in .env")

    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_path and Path(sa_path).is_file():
        return spreadsheet_id, sa_path, None

    repo_sa = _REPO_ROOT / "service-account.json"
    if repo_sa.is_file():
        return spreadsheet_id, str(repo_sa), None

    inline = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_INLINE", "").strip()
    if inline:
        import json

        return spreadsheet_id, None, json.loads(inline)

    raise SystemExit("service-account.json not found in repo root and GOOGLE_SERVICE_ACCOUNT_JSON not set")


def _list_sheet_titles(sheet: SheetWrapper) -> set[str]:
    meta = sheet._execute_with_retries(  # noqa: SLF001
        lambda: sheet.service.spreadsheets().get(spreadsheetId=sheet.spreadsheet_id, fields="sheets.properties.title")
    )
    return {item["properties"]["title"] for item in meta.get("sheets", [])}


def _create_tab(sheet: SheetWrapper, tab_name: str) -> None:
    sheet._execute_with_retries(  # noqa: SLF001
        lambda: sheet.service.spreadsheets().batchUpdate(
            spreadsheetId=sheet.spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
        )
    )
    print(f"CREATED tab: {tab_name}")


def _write_header_row(sheet: SheetWrapper, tab_name: str, headers: tuple[str, ...]) -> None:
    row = [list(headers)]
    sheet._execute_with_retries(  # noqa: SLF001
        lambda: sheet.service.spreadsheets().values().update(
            spreadsheetId=sheet.spreadsheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            body={"values": row},
        )
    )
    sheet._tab_cache.pop(tab_name, None)  # noqa: SLF001
    print(f"HEADERS tab={tab_name} cols={len(headers)}")


def _tab_has_headers(sheet: SheetWrapper, tab_name: str) -> bool:
    try:
        values = sheet._fetch_values(tab_name)  # noqa: SLF001
    except Exception:
        return False
    return bool(values and values[0])


def bootstrap(*, seed_kpi: bool = True) -> int:
    spreadsheet_id, sa_path, sa_info = _resolve_credentials()
    sheet = SheetWrapper(spreadsheet_id, service_account_json_path=sa_path, service_account_info=sa_info)
    existing = _list_sheet_titles(sheet)

    for tab_name in BOOTSTRAP_TABS:
        schema = TAB_SCHEMAS[tab_name]
        if tab_name not in existing:
            _create_tab(sheet, tab_name)
            existing.add(tab_name)

        if not _tab_has_headers(sheet, tab_name):
            _write_header_row(sheet, tab_name, schema.required_columns)
        else:
            print(f"SKIP tab={tab_name} (headers already present)")

    if seed_kpi:
        rows = sheet.read_tab("kpi_targets")
        if not rows:
            sheet.append_row("kpi_targets", KPI_SEED_ROW, unique_key="target_id")
            print("SEEDED kpi_targets example row")
        else:
            print(f"SKIP kpi seed ({len(rows)} rows exist)")

    print("DONE bootstrap")
    return 0


def main() -> None:
    code = bootstrap()
    sys.exit(code)


if __name__ == "__main__":
    main()
