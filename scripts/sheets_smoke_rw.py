"""Phase-0 smoke test for Google Sheets read/write access.

Reads the header from `staff_users` and appends a technical proof row to `audit_log`.

Required env vars:
  - SPREADSHEET_ID
  - GOOGLE_SERVICE_ACCOUNT_JSON

Optional env vars:
  - AUDIT_TAB (default: audit_log)
  - SMOKE_PROOF_PATH (default: artifacts/phase0_rw_smoke_result.json)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "").strip()
SA_JSON_PATH = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
AUDIT_TAB = os.environ.get("AUDIT_TAB", "audit_log").strip() or "audit_log"
PROOF_PATH = (
    os.environ.get("SMOKE_PROOF_PATH", "artifacts/phase0_rw_smoke_result.json").strip()
    or "artifacts/phase0_rw_smoke_result.json"
)


def fail(message: str) -> "None":
    """Stop execution with a consistent error format."""
    raise SystemExit(f"[FAIL] {message}")


def write_proof(payload: dict[str, Any]) -> None:
    """Write smoke result proof JSON to disk for changelog/README updates."""
    target = Path(PROOF_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_client():
    """Build an authenticated Google Sheets API client."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(SA_JSON_PATH, scopes=scopes)
    return build("sheets", "v4", credentials=credentials)


def main() -> None:
    """Run Phase-0 smoke: read staff_users header and append into audit_log."""
    if not SPREADSHEET_ID:
        fail("SPREADSHEET_ID is empty")
    if not SA_JSON_PATH:
        fail("GOOGLE_SERVICE_ACCOUNT_JSON is empty")
    if not os.path.exists(SA_JSON_PATH):
        fail(f"Service account JSON not found: {SA_JSON_PATH}")

    try:
        service = build_client()

        read_range = "staff_users!A1:Z1"
        response = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=read_range,
        ).execute()
        header = (response.get("values") or [[]])[0]
        if not header or len(header) < 3:
            fail(
                "staff_users header is empty or too short. "
                "Check tab name and header row."
            )

        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        diff = {
            "check": "phase0_rw_smoke",
            "read_range": read_range,
            "staff_users_columns": header[:10],
            "result": "OK",
        }
        row = [
            timestamp,
            "system_smoke",
            "create",
            "sheet_access_test",
            SPREADSHEET_ID,
            json.dumps(diff, ensure_ascii=False),
        ]

        append_range = f"{AUDIT_TAB}!A:F"
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=append_range,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        proof = {
            "status": "PASS",
            "timestamp": timestamp,
            "spreadsheet_id": SPREADSHEET_ID,
            "audit_tab": AUDIT_TAB,
            "read_range": read_range,
            "entity": "sheet_access_test",
            "action": "create",
            "actor": "system_smoke",
        }
        write_proof(proof)

        print("[OK] Read staff_users header + appended audit_log row.")
        print(f"      audit_tab={AUDIT_TAB}, ts={timestamp}")
        print(f"      proof_file={PROOF_PATH}")
        print("[NEXT] README line:")
        print(f"      Phase 0 RW smoke PASS (ts={timestamp})")
        print("[NEXT] CHANGELOG line:")
        print(
            "      2026-04-18: Phase 0 RW smoke PASS, "
            f"audit_log row created, ts={timestamp}"
        )

    except HttpError as exc:
        fail(f"Google Sheets API error: {exc}")


if __name__ == "__main__":
    main()
