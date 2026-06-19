from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "icebeach-wakeclub"
API_DIR = REPO_ROOT / "apps" / "api"

os.chdir(API_DIR)
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings
from app.services.preflight import run_preflight_check
from packages.sheets import SheetWrapper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight integrity check for Ice Beach Wake Club")
    parser.add_argument("--date", dest="target_date", required=True, help="Shift date in YYYY-MM-DD format")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    sheet = SheetWrapper(settings.spreadsheet_id, settings.service_account_json_path)
    report = run_preflight_check(sheet, target_date=args.target_date)

    for item in report["checks"]:
        print(f"[{item['level']}] {item['code']}: {item['message']}")

    print(f"SUMMARY blockers={report['blockers']} warnings={report['warnings']}")
    return 1 if int(report["blockers"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
