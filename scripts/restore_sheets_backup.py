from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Callable, Mapping

# Env names of spreadsheets that a restore must never overwrite by accident.
PROTECTED_SPREADSHEET_ENV_NAMES = ("SPREADSHEET_ID", "INTAKE_SPREADSHEET_ID")
ALLOW_PROD_TARGET_FLAG = "--allow-prod-target"


class RestoreTargetRefused(RuntimeError):
    """Raised when --write targets an empty or protected (production) spreadsheet."""


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


def collect_protected_spreadsheet_ids(
    env: Mapping[str, str] | None = None,
    settings: object | None = None,
) -> dict[str, str]:
    """Return {env_name: spreadsheet_id} for production spreadsheets (env + app settings)."""
    env = os.environ if env is None else env
    protected: dict[str, str] = {}
    for name in PROTECTED_SPREADSHEET_ENV_NAMES:
        value = (env.get(name) or "").strip()
        if value:
            protected[name] = value
    if settings is not None:
        for name, attr in (("SPREADSHEET_ID", "spreadsheet_id"), ("INTAKE_SPREADSHEET_ID", "intake_spreadsheet_id")):
            value = (getattr(settings, attr, None) or "").strip()
            if value and value not in protected.values():
                key = name if name not in protected else f"settings.{attr}"
                protected[key] = value
    return protected


def confirmation_phrase(protected_name: str) -> str:
    return f"OVERWRITE {protected_name}"


def check_write_target(
    target_spreadsheet_id: str,
    protected: Mapping[str, str],
    *,
    allow_prod_target: bool = False,
    input_func: Callable[[str], str] = input,
    is_interactive: bool | None = None,
) -> str:
    """Validate the --write target. Returns the normalized id or raises RestoreTargetRefused."""
    target = (target_spreadsheet_id or "").strip()
    if not target:
        raise RestoreTargetRefused("--target-spreadsheet-id is required with --write")

    matches = [name for name, value in protected.items() if value == target]
    if not matches:
        return target

    names = ", ".join(matches)
    if not allow_prod_target:
        raise RestoreTargetRefused(
            f"target spreadsheet equals production {names}; restore --write into a separate "
            f"test spreadsheet. Disaster recovery only: add {ALLOW_PROD_TARGET_FLAG} and type the confirmation."
        )

    if is_interactive is None:
        is_interactive = sys.stdin.isatty()
    if not is_interactive:
        raise RestoreTargetRefused(
            f"{ALLOW_PROD_TARGET_FLAG} requires an interactive terminal to type the confirmation"
        )
    phrase = confirmation_phrase(matches[0])
    print(
        f"WARNING: --write will CLEAR and overwrite production {names} from this backup.",
        file=sys.stderr,
    )
    try:
        typed = input_func(f"Type '{phrase}' to continue: ")
    except EOFError:
        typed = ""
    if (typed or "").strip() != phrase:
        raise RestoreTargetRefused("confirmation phrase mismatch; nothing was written")
    return target


def _load_protected_from_app_settings() -> dict[str, str]:
    # Importing config loads the repo .env (same as the API), then env + settings are both checked.
    from apps.api.app.config import get_settings

    try:
        settings = get_settings()
    except RuntimeError:
        settings = None
    return collect_protected_spreadsheet_ids(os.environ, settings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or restore a Ruza Sheets JSON backup.")
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--target-spreadsheet-id", default="")
    parser.add_argument("--write", action="store_true", help="Actually write values to target spreadsheet")
    parser.add_argument(
        ALLOW_PROD_TARGET_FLAG,
        dest="allow_prod_target",
        action="store_true",
        help=(
            "Disaster recovery only: allow --write into SPREADSHEET_ID / INTAKE_SPREADSHEET_ID. "
            "Requires typing 'OVERWRITE <ENV_NAME>' in an interactive terminal."
        ),
    )
    args = parser.parse_args(argv)

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

    try:
        if not args.target_spreadsheet_id.strip():
            raise RestoreTargetRefused("--target-spreadsheet-id is required with --write")
        try:
            protected = _load_protected_from_app_settings()
        except ImportError as exc:
            raise RestoreTargetRefused(
                f"cannot load app settings to verify the target is not production ({exc}); "
                "set PYTHONPATH=icebeach-wakeclub and install API requirements"
            ) from exc
        target_id = check_write_target(
            args.target_spreadsheet_id,
            protected,
            allow_prod_target=args.allow_prod_target,
        )
    except RestoreTargetRefused as exc:
        print(f"RESTORE_REFUSED: {exc}", file=sys.stderr)
        return 2

    from apps.api.app.config import get_settings
    from packages.sheets import SheetWrapper

    settings = get_settings()
    sheet = SheetWrapper(
        target_id,
        settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )
    spreadsheet = sheet._execute_with_retries(
        lambda: sheet.service.spreadsheets().get(spreadsheetId=target_id)
    )
    existing_titles = {
        item.get("properties", {}).get("title", "")
        for item in spreadsheet.get("sheets", [])
    }
    missing_tabs = [title for title, _values in restored_tabs if title not in existing_titles]
    if missing_tabs:
        sheet._execute_with_retries(
            lambda: sheet.service.spreadsheets().batchUpdate(
                spreadsheetId=target_id,
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
                spreadsheetId=target_id,
                range=f"{title}!A1:ZZ",
            )
        )
        if values:
            end_col = _column_letter(max(len(row) for row in values))
            sheet._execute_with_retries(
                lambda title=title, values=values, end_col=end_col: sheet.service.spreadsheets().values().update(
                    spreadsheetId=target_id,
                    range=f"{title}!A1:{end_col}{len(values)}",
                    valueInputOption="RAW",
                    body={"values": values},
                )
            )
        print(f"RESTORED tab={title} rows={len(values)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
