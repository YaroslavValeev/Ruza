"""Print active staff_users from Google Sheets (for local login recovery)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from packages.sheets.bootstrap_tabs import _resolve_credentials
from packages.sheets.sheet_wrapper import SheetWrapper

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_REPO_ROOT / ".env.docker")

ACTIVE = {"1", "true", "yes", "y"}


def main() -> None:
    spreadsheet_id, sa_path, sa_info = _resolve_credentials()
    sheet = SheetWrapper(spreadsheet_id, service_account_json_path=sa_path, service_account_info=sa_info)
    rows = sheet.read_tab("staff_users")
    active = [r for r in rows if str(r.get("is_active", "")).strip().lower() in ACTIVE]

    if not active:
        print("Нет активных staff_users в Sheets.")
        sys.exit(1)

    print("=== Активные сотрудники (логин в Dashboard) ===")
    print("Вход: staff_user_id + телефон → код (в dev код показывается на экране)")
    print()
    for row in sorted(active, key=lambda r: (r.get("role", ""), r.get("staff_user_id", ""))):
        print(f"  {row.get('full_name', '?')}")
        print(f"    staff_user_id: {row.get('staff_user_id', '')}")
        print(f"    телефон:       {row.get('phone', '')}")
        print(f"    роль:          {row.get('role', '')}")
        if row.get("boat_id") or row.get("pilot_user_id"):
            print(f"    лодка/pilot:   {row.get('boat_id') or row.get('pilot_user_id', '')}")
        print()

    print("Mobile:")
    print("  pilot → /m/pilot   (роли: pilot, admin, operator)")
    print("  owner → /m/owner   (роли: admin, operator)")


if __name__ == "__main__":
    main()
