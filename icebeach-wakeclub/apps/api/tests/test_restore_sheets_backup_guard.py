from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "restore_sheets_backup.py"

PROD_SHEET = "prod-main-sheet-id"
PROD_INTAKE = "prod-intake-sheet-id"
TEST_SHEET = "separate-test-sheet-id"


def _load_restore_module():
    spec = importlib.util.spec_from_file_location("restore_sheets_backup", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


restore = _load_restore_module()


def _write_backup(backup_dir: Path) -> None:
    tabs_dir = backup_dir / "tabs"
    tabs_dir.mkdir(parents=True)
    values_path = tabs_dir / "clients.json"
    values_path.write_text(
        json.dumps([["client_id", "full_name"], ["client-test-001", "Smoke Client"]]),
        encoding="utf-8",
    )
    manifest = {
        "created_at": "20261007T000000Z",
        "spreadsheet_id": "source-test-sheet",
        "tabs": [
            {
                "name": "clients",
                "rows": 2,
                "columns": 2,
                "file": "tabs/clients.json",
                "sha256": hashlib.sha256(values_path.read_bytes()).hexdigest(),
            }
        ],
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class _FakeSheetWrapper:
    instances: list["_FakeSheetWrapper"] = []

    def __init__(self, spreadsheet_id, service_account_json_path, service_account_info=None):
        self.spreadsheet_id = spreadsheet_id
        self.calls: list[tuple[str, str]] = []
        self.service = self
        _FakeSheetWrapper.instances.append(self)

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId):
        self.calls.append(("get", spreadsheetId))
        return {"sheets": [{"properties": {"title": "clients"}}]}

    def batchUpdate(self, spreadsheetId, body):
        self.calls.append(("batchUpdate", spreadsheetId))
        return {}

    def clear(self, spreadsheetId, range):
        self.calls.append(("clear", spreadsheetId))
        return {}

    def update(self, spreadsheetId, range, valueInputOption, body):
        self.calls.append(("update", spreadsheetId))
        return {}

    def _execute_with_retries(self, request_factory):
        return request_factory()


@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("SPREADSHEET_ID", PROD_SHEET)
    monkeypatch.setenv("INTAKE_SPREADSHEET_ID", PROD_INTAKE)
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(Path(__file__).resolve()))
    monkeypatch.setenv("APP_ENV", "test")
    import packages.sheets

    _FakeSheetWrapper.instances = []
    monkeypatch.setattr(packages.sheets, "SheetWrapper", _FakeSheetWrapper)
    return monkeypatch


@pytest.fixture
def backup_dir(tmp_path):
    path = tmp_path / "backup"
    _write_backup(path)
    return path


# --- unit: check_write_target -------------------------------------------------

PROTECTED = {"SPREADSHEET_ID": PROD_SHEET, "INTAKE_SPREADSHEET_ID": PROD_INTAKE}


@pytest.mark.parametrize("target", ["", "   "])
def test_empty_target_refused(target):
    with pytest.raises(restore.RestoreTargetRefused, match="required"):
        restore.check_write_target(target, PROTECTED)


@pytest.mark.parametrize("target", ["", "  "])
def test_empty_target_refused_even_with_override(target):
    with pytest.raises(restore.RestoreTargetRefused, match="required"):
        restore.check_write_target(target, PROTECTED, allow_prod_target=True, is_interactive=True)


@pytest.mark.parametrize(
    ("target", "env_name"),
    [(PROD_SHEET, "SPREADSHEET_ID"), (f"  {PROD_INTAKE} ", "INTAKE_SPREADSHEET_ID")],
)
def test_production_targets_refused(target, env_name):
    with pytest.raises(restore.RestoreTargetRefused, match=env_name):
        restore.check_write_target(target, PROTECTED)


def test_separate_test_target_allowed():
    assert restore.check_write_target(f" {TEST_SHEET} ", PROTECTED) == TEST_SHEET


def test_override_requires_interactive_terminal():
    with pytest.raises(restore.RestoreTargetRefused, match="interactive"):
        restore.check_write_target(
            PROD_SHEET,
            PROTECTED,
            allow_prod_target=True,
            input_func=lambda _prompt: "OVERWRITE SPREADSHEET_ID",
            is_interactive=False,
        )


def test_override_wrong_confirmation_refused():
    with pytest.raises(restore.RestoreTargetRefused, match="mismatch"):
        restore.check_write_target(
            PROD_SHEET,
            PROTECTED,
            allow_prod_target=True,
            input_func=lambda _prompt: "yes",
            is_interactive=True,
        )


def test_override_eof_refused():
    def _eof(_prompt):
        raise EOFError

    with pytest.raises(restore.RestoreTargetRefused, match="mismatch"):
        restore.check_write_target(
            PROD_INTAKE, PROTECTED, allow_prod_target=True, input_func=_eof, is_interactive=True
        )


def test_override_with_exact_confirmation_allowed():
    assert (
        restore.check_write_target(
            PROD_INTAKE,
            PROTECTED,
            allow_prod_target=True,
            input_func=lambda _prompt: "OVERWRITE INTAKE_SPREADSHEET_ID",
            is_interactive=True,
        )
        == PROD_INTAKE
    )


def test_protected_ids_from_env_and_settings():
    class _Settings:
        spreadsheet_id = "settings-main"
        intake_spreadsheet_id = None

    protected = restore.collect_protected_spreadsheet_ids(
        {"SPREADSHEET_ID": " env-main ", "INTAKE_SPREADSHEET_ID": "env-intake"}, _Settings()
    )
    assert set(protected.values()) == {"env-main", "env-intake", "settings-main"}
    assert restore.collect_protected_spreadsheet_ids({"SPREADSHEET_ID": "", "INTAKE_SPREADSHEET_ID": "  "}) == {}


# --- end-to-end: main() ---------------------------------------------------------


@pytest.mark.parametrize("target", [PROD_SHEET, PROD_INTAKE])
def test_main_write_to_production_exits_nonzero_without_google_calls(prod_env, backup_dir, target, capsys):
    code = restore.main(["--backup-dir", str(backup_dir), "--write", "--target-spreadsheet-id", target])
    captured = capsys.readouterr()
    assert code != 0
    assert "RESTORE_REFUSED" in captured.err
    assert _FakeSheetWrapper.instances == []


def test_main_write_without_target_exits_nonzero(prod_env, backup_dir, capsys):
    code = restore.main(["--backup-dir", str(backup_dir), "--write"])
    captured = capsys.readouterr()
    assert code != 0
    assert "--target-spreadsheet-id is required with --write" in captured.err
    assert _FakeSheetWrapper.instances == []


def test_main_override_non_interactive_refused(prod_env, backup_dir, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    code = restore.main(
        ["--backup-dir", str(backup_dir), "--write", "--allow-prod-target", "--target-spreadsheet-id", PROD_SHEET]
    )
    assert code != 0
    assert "interactive" in capsys.readouterr().err
    assert _FakeSheetWrapper.instances == []


def test_main_write_to_separate_test_sheet_proceeds(prod_env, backup_dir, capsys):
    code = restore.main(["--backup-dir", str(backup_dir), "--write", "--target-spreadsheet-id", TEST_SHEET])
    out = capsys.readouterr().out
    assert code == 0
    assert "RESTORED tab=clients rows=2" in out
    assert len(_FakeSheetWrapper.instances) == 1
    sheet = _FakeSheetWrapper.instances[0]
    assert sheet.spreadsheet_id == TEST_SHEET
    assert {spreadsheet_id for _op, spreadsheet_id in sheet.calls} == {TEST_SHEET}


def test_main_dry_run_unaffected(prod_env, backup_dir, capsys):
    code = restore.main(["--backup-dir", str(backup_dir), "--target-spreadsheet-id", PROD_SHEET])
    out = capsys.readouterr().out
    assert code == 0
    assert "BACKUP_OK tabs=1" in out and "DRY_RUN only" in out
    assert _FakeSheetWrapper.instances == []
