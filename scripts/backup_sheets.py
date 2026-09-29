from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from apps.api.app.config import get_settings
from packages.sheets import SheetWrapper


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up Ruza Google Sheets tabs to local JSON files.")
    parser.add_argument("--spreadsheet-id", default="", help="Override SPREADSHEET_ID from .env")
    parser.add_argument("--out-dir", default="backups/sheets", help="Backup root directory")
    args = parser.parse_args()

    settings = get_settings()
    spreadsheet_id = args.spreadsheet_id.strip() or settings.spreadsheet_id
    sheet = SheetWrapper(
        spreadsheet_id,
        settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )
    created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(args.out_dir) / created_at
    tabs_dir = backup_dir / "tabs"
    tabs_dir.mkdir(parents=True, exist_ok=True)

    spreadsheet = sheet._execute_with_retries(
        lambda: sheet.service.spreadsheets().get(spreadsheetId=spreadsheet_id)
    )
    manifest: dict[str, object] = {
        "created_at": created_at,
        "spreadsheet_id": spreadsheet_id,
        "tabs": [],
    }

    for tab in spreadsheet.get("sheets", []):
        title = tab.get("properties", {}).get("title", "")
        if not title:
            continue
        values = sheet._execute_with_retries(
            lambda title=title: sheet.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{title}!A1:ZZ",
            )
        ).get("values", [])
        path = tabs_dir / f"{title}.json"
        path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        tab_info = {
            "name": title,
            "rows": len(values),
            "columns": max((len(row) for row in values), default=0),
            "file": str(path.relative_to(backup_dir)).replace("\\", "/"),
            "sha256": _sha256(path),
        }
        manifest["tabs"].append(tab_info)

    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"BACKUP_DIR={backup_dir}")
    print(f"TABS={len(manifest['tabs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
