"""One-off restore proof; run only against an approved non-production target."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load verified restore helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _single_manifest(root: Path) -> Path:
    paths = list(root.glob("*/manifest.json"))
    if len(paths) != 1:
        raise RuntimeError("Expected exactly one completed snapshot")
    return paths[0].parent


def _compare(source: Path, actual: Path) -> dict[str, int | str]:
    expected_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    actual_manifest = json.loads((actual / "manifest.json").read_text(encoding="utf-8"))
    restored = {tab["name"]: tab for tab in actual_manifest["tabs"]}
    if not expected_manifest["tabs"]:
        raise RuntimeError("Empty source backup cannot prove recovery")
    cells = 0
    for tab in expected_manifest["tabs"]:
        if tab["name"] not in restored:
            raise RuntimeError("Restore verification failed: a tab is missing")
        expected_values = json.loads((source / tab["file"]).read_text(encoding="utf-8"))
        actual_values = json.loads((actual / restored[tab["name"]]["file"]).read_text(encoding="utf-8"))
        # Python considers True == 1; recovery proof must preserve JSON types.
        if json.dumps(expected_values, allow_nan=False) != json.dumps(actual_values, allow_nan=False):
            raise RuntimeError("Restore verification failed: cell values differ")
        cells += sum(len(row) for row in expected_values)
    return {"status": "PASS", "tabs": len(expected_manifest["tabs"]), "cells": cells}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "restore", "after"), required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--target-spreadsheet-id", required=True)
    parser.add_argument("--expected-target-title", required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    root = Path(args.work_dir)
    restore = _load("restore_proof_helper", root / "restore_sheets_backup.py")
    target = restore.check_write_target(args.target_spreadsheet_id, restore._load_protected_from_app_settings())

    from apps.api.app.config import get_settings
    import packages.sheets

    settings = get_settings()
    source = root / "source"
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("spreadsheet_id") != settings.spreadsheet_id:
        raise RuntimeError("Source must be the operational backup")
    restore.main(["--backup-dir", str(source)])
    backup = _load("quota_backup_helper", root / "backup_sheets.py")
    original_wrapper = packages.sheets.SheetWrapper

    def make_sheet(spreadsheet_id, *positional, **keywords):
        if spreadsheet_id != target:
            raise RuntimeError("Restore proof may access only its approved target")
        sheet = original_wrapper(spreadsheet_id, *positional, **keywords)
        execute = sheet._execute_with_retries
        reader = backup._BackupReader(SimpleNamespace(_execute_with_retries=execute))
        # This process only: clear/update are idempotent, and metadata failure
        # still stops before clear. The running API transport is not modified.
        sheet._execute_with_retries = lambda factory, **_kwargs: reader.read(factory)
        return sheet

    sheet = make_sheet(target, settings.service_account_json_path, service_account_info=settings.service_account_info)
    metadata = sheet._execute_with_retries(lambda: sheet.service.spreadsheets().get(
        spreadsheetId=target, fields="properties.title,sheets.properties",
    ))
    if metadata["properties"]["title"] != args.expected_target_title:
        raise RuntimeError("Unexpected test target title")

    if args.phase == "before":
        (root / "target-metadata-before.json").write_text(json.dumps(metadata), encoding="utf-8")
    elif not (root / "snapshot-persisted").is_file():
        raise RuntimeError("Persist and verify the pre-test snapshot on the host first")

    if args.phase == "restore":
        restore.main(["--backup-dir", str(_single_manifest(root / "before"))])
        packages.sheets.SheetWrapper = make_sheet
        try:
            return restore.main(["--backup-dir", str(source), "--write", "--target-spreadsheet-id", target])
        finally:
            packages.sheets.SheetWrapper = original_wrapper

    import sys

    previous_args = sys.argv
    sys.argv = ["backup_sheets.py", "--spreadsheet-id", target, "--out-dir", str(root / args.phase)]
    try:
        backup.main()
    finally:
        sys.argv = previous_args
    snapshot = _single_manifest(root / args.phase)
    restore.main(["--backup-dir", str(snapshot)])
    if args.phase == "after":
        proof = _compare(source, snapshot)
        proof["verified_at"] = datetime.now(timezone.utc).isoformat()
        (root / "proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(f"RESTORE_WRITE_READBACK_PASS tabs={proof['tabs']} cells={proof['cells']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
