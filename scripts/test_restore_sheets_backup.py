from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_restore(repo_root: Path, backup_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "icebeach-wakeclub")
    return subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "restore_sheets_backup.py"),
            "--backup-dir",
            str(backup_dir),
            *extra_args,
        ],
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _write_backup(backup_dir: Path) -> Path:
    tabs_dir = backup_dir / "tabs"
    tabs_dir.mkdir(parents=True)
    values_path = tabs_dir / "clients.json"
    values_path.write_text(
        json.dumps(
            [
                ["client_id", "full_name", "phone"],
                ["client-test-001", "Smoke Client", "+70000000000"],
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest = {
        "created_at": "20260916T000000Z",
        "spreadsheet_id": "source-test-sheet",
        "tabs": [
            {
                "name": "clients",
                "rows": 2,
                "columns": 3,
                "file": "tabs/clients.json",
                "sha256": _sha256(values_path),
            }
        ],
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return values_path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="ruza-restore-proof-") as tmp:
        backup_dir = Path(tmp) / "backup"
        values_path = _write_backup(backup_dir)

        dry_run = _run_restore(repo_root, backup_dir)
        print(dry_run.stdout)
        if dry_run.returncode != 0:
            print("[BLOCKER] restore dry-run failed")
            return 1
        if "BACKUP_OK tabs=1" not in dry_run.stdout or "DRY_RUN only" not in dry_run.stdout:
            print("[BLOCKER] restore dry-run did not report expected proof lines")
            return 1

        write_without_target = _run_restore(repo_root, backup_dir, "--write")
        print(write_without_target.stdout)
        if write_without_target.returncode == 0 or "--target-spreadsheet-id is required with --write" not in write_without_target.stdout:
            print("[BLOCKER] restore write without target was not blocked")
            return 1

        values_path.write_text('["corrupted"]\n', encoding="utf-8")
        corrupted = _run_restore(repo_root, backup_dir)
        print(corrupted.stdout)
        if corrupted.returncode == 0 or "Backup file hash mismatch" not in corrupted.stdout:
            print("[BLOCKER] restore accepted corrupted backup")
            return 1

    print("[PASS] restore backup behavior verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
