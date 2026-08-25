from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from apps.api.app.config import get_settings
from packages.sheets import SheetWrapper


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _column_letter(column_number: int) -> str:
    result = []
    while column_number > 0:
        column_number, rem = divmod(column_number - 1, 26)
        result.append(chr(65 + rem))
    return "".join(reversed(result))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or restore a Ruza Sheets JSON backup.")
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--target-spreadsheet-id", default="")
    parser.add_argument("--write", action="store_true", help="Actually write values to target spreadsheet")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    restored_tabs = []
    for tab in manifest.get("tabs", []):
        path = backup_dir / str(tab["file"])
        actual_hash = _sha256(path)
        if actual_hash != tab["sha256"]:
            raise RuntimeError(f"Backup file hash mismatch: {path}")
        values = json.loads(path.read_text(encoding="utf-8"))
        restored_tabs.append((str(tab["name"]), values))

    print(f"BACKUP_OK tabs={len(restored_tabs)}")
    if not args.write:
        print("DRY_RUN only. Add --write and --target-spreadsheet-id to restore.")
        return 0

    if not args.target_spreadsheet_id.strip():
        raise RuntimeError("--target-spreadsheet-id is required with --write")

    settings = get_settings()
    sheet = SheetWrapper(
        args.target_spreadsheet_id.strip(),
        settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )
    spreadsheet = sheet._execute_with_retries(
        lambda: sheet.service.spreadsheets().get(spreadsheetId=args.target_spreadsheet_id.strip())
    )
    existing_titles = {
        item.get("properties", {}).get("title", "")
        for item in spreadsheet.get("sheets", [])
    }
    missing_tabs = [title for title, _values in restored_tabs if title not in existing_titles]
    if missing_tabs:
        sheet._execute_with_retries(
            lambda: sheet.service.spreadsheets().batchUpdate(
                spreadsheetId=args.target_spreadsheet_id.strip(),
                body={
                    "requests": [
                        {"addSheet": {"properties": {"title": title}}}
                        for title in missing_tabs
                    ]
                },
            )
        )

    for title, values in restored_tabs:
        sheet._execute_with_retries(
            lambda title=title: sheet.service.spreadsheets().values().clear(
                spreadsheetId=args.target_spreadsheet_id.strip(),
                range=f"{title}!A1:ZZ",
            )
        )
        if values:
            end_col = _column_letter(max(len(row) for row in values))
            sheet._execute_with_retries(
                lambda title=title, values=values, end_col=end_col: sheet.service.spreadsheets().values().update(
                    spreadsheetId=args.target_spreadsheet_id.strip(),
                    range=f"{title}!A1:{end_col}{len(values)}",
                    valueInputOption="RAW",
                    body={"values": values},
                )
            )
        print(f"RESTORED tab={title} rows={len(values)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
