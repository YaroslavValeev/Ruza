from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.errors import HttpError

from apps.api.app.config import get_settings
from packages.sheets import SheetWrapper


logger = logging.getLogger(__name__)


def _retryable_http_error(exc: HttpError) -> bool:
    if int(exc.resp.status) in {429, 500, 502, 503, 504}:
        return True
    if int(exc.resp.status) != 403:
        return False
    try:
        payload = json.loads(exc.content)
        errors = payload["error"]["errors"]
    except (ValueError, TypeError, KeyError):
        return False
    return isinstance(errors, list) and any(
        isinstance(error, dict) and error.get("reason") in {"rateLimitExceeded", "userRateLimitExceeded"}
        for error in errors
    )


class _BackupReader:
    """Keep backup traffic below quota without changing the live API transport."""

    def __init__(self, sheet: SheetWrapper) -> None:
        self.sheet = sheet
        self.next_read_at = 0.0

    def read(self, request_factory):
        for attempt in range(8):
            delay = self.next_read_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.next_read_at = time.monotonic() + 2.0
            try:
                return self.sheet._execute_with_retries(request_factory, attempts=1)
            except (HttpError, OSError) as exc:
                status = int(exc.resp.status) if isinstance(exc, HttpError) else 0
                if isinstance(exc, HttpError) and not _retryable_http_error(exc):
                    raise
                if attempt == 7:
                    raise RuntimeError(f"Backup read failed after 8 attempts (HTTP {status or 'transport'})") from None
                wait = min(2**attempt + random.uniform(0, 1), 64.0)
                if isinstance(exc, HttpError):
                    retry_after = str(exc.resp.get("retry-after", ""))
                    if retry_after.isdigit():
                        wait = max(wait, min(int(retry_after), 300))
                logger.warning("Backup read retry: status=%s attempt=%s wait=%.1fs", status, attempt + 1, wait)
                time.sleep(wait)


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
    reader = _BackupReader(sheet)
    created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(args.out_dir) / created_at
    tabs_dir = backup_dir / "tabs"
    tabs_dir.mkdir(parents=True, exist_ok=True)

    spreadsheet = reader.read(
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
        quoted_title = "'" + title.replace("'", "''") + "'"
        values = reader.read(
            lambda quoted_title=quoted_title: sheet.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{quoted_title}!A1:ZZ",
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
