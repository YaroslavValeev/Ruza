from __future__ import annotations

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "restore_sheets_backup.py"
PROTECTED = {
    "SPREADSHEET_ID": "synthetic-production-main",
    "INTAKE_SPREADSHEET_ID": "synthetic-production-intake",
}
TEST_SHEET = "synthetic-nonproduction-restore-target"


def _load_restore_module():
    spec = importlib.util.spec_from_file_location("restore_sheets_grid_capacity", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


restore = _load_restore_module()


def _write_backup(tmp_path, tabs):
    backup_dir = tmp_path / "backup"
    (backup_dir / "tabs").mkdir(parents=True)
    manifest = {"spreadsheet_id": "synthetic-backup-source", "tabs": []}
    for index, (title, values) in enumerate(tabs.items()):
        relative_path = f"tabs/{index}.json"
        path = backup_dir / relative_path
        path.write_text(json.dumps(values), encoding="utf-8")
        manifest["tabs"].append({
            "name": title,
            "rows": len(values),
            "columns": max((len(row) for row in values), default=0),
            "file": relative_path,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (backup_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return backup_dir


def _properties(title, sheet_id, rows, columns):
    return {
        "title": title,
        "sheetId": sheet_id,
        "gridProperties": {"rowCount": rows, "columnCount": columns},
    }


def _large_values():
    # The widest row is last, so neither the header nor the first data row suffices.
    return [["synthetic-row"] for _ in range(1200)] + [
        [f"synthetic-column-{column}" for column in range(40)]
    ]


class _FakeSheetWrapper:
    def __init__(self, spreadsheet_id, service_account_json_path, service_account_info, state):
        assert spreadsheet_id == TEST_SHEET
        assert service_account_json_path == "offline-unused-credentials.json"
        assert service_account_info is None
        self.spreadsheet_id = spreadsheet_id
        self.state = state
        self.calls = []
        self.service = self
        self.stored_values = {item["title"]: [["original-value"]] for item in state.sheets}
        state.instances.append(self)

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def _record(self, operation, spreadsheet_id, **payload):
        assert spreadsheet_id == TEST_SHEET
        self.calls.append((operation, deepcopy(payload)))

    def get(self, spreadsheetId, **kwargs):
        self._record("get", spreadsheetId, **kwargs)
        return {"sheets": [{"properties": deepcopy(item)} for item in self.state.sheets]}

    def batchUpdate(self, spreadsheetId, body):
        self._record("metadata", spreadsheetId, body=body)
        assert body["requests"], "An empty metadata batch must not be sent"
        if self.state.fail_metadata:
            raise RuntimeError("synthetic metadata resize failure")
        return {}

    def clear(self, spreadsheetId, range):
        self._record("clear", spreadsheetId, range=range)
        self.stored_values[range] = []
        return {}

    def update(self, spreadsheetId, range, valueInputOption, body):
        self._record("update", spreadsheetId, range=range, valueInputOption=valueInputOption, body=body)
        self.stored_values[range] = deepcopy(body["values"])
        return {}

    def _execute_with_retries(self, request_factory):
        return request_factory()


@pytest.fixture
def offline_restore(monkeypatch):
    import apps.api.app.config as config
    import packages.sheets

    state = SimpleNamespace(sheets=[], instances=[], fail_metadata=False, settings_calls=[])

    def get_settings():
        state.settings_calls.append(True)
        return SimpleNamespace(
            service_account_json_path="offline-unused-credentials.json",
            service_account_info=None,
        )

    def make_wrapper(spreadsheet_id, service_account_json_path, service_account_info=None):
        return _FakeSheetWrapper(spreadsheet_id, service_account_json_path, service_account_info, state)

    monkeypatch.setattr(packages.sheets, "SheetWrapper", make_wrapper)
    monkeypatch.setattr(config, "get_settings", get_settings)
    monkeypatch.setattr(restore, "_load_protected_from_app_settings", lambda: dict(PROTECTED))
    return state


def _run(backup_dir, *, write=True, target=TEST_SHEET):
    args = ["--backup-dir", str(backup_dir)]
    if target is not None:
        args.extend(["--target-spreadsheet-id", target])
    if write:
        args.append("--write")
    return restore.main(args)


def _metadata_requests(sheet):
    batches = [payload["body"]["requests"] for operation, payload in sheet.calls if operation == "metadata"]
    assert len(batches) == 1
    operations = [operation for operation, _payload in sheet.calls]
    assert operations[0] == "get"
    metadata_index = operations.index("metadata")
    assert all(metadata_index < index for index, operation in enumerate(operations) if operation in {"clear", "update"})
    assert "clear" in operations
    return batches[0]


@pytest.mark.parametrize("rows", [1000, 1201, 2000], ids=["rows-small", "rows-equal", "rows-large"])
@pytest.mark.parametrize("columns", [26, 40, 60], ids=["cols-small", "cols-equal", "cols-large"])
@pytest.mark.parametrize("write", [True, False], ids=["write", "dry-run"])
def test_existing_grid_capacity_matrix(tmp_path, offline_restore, rows, columns, write, capsys):
    values = _large_values()
    backup_dir = _write_backup(tmp_path, {"clients": values})
    offline_restore.sheets = [_properties("clients", 17, rows, columns)]

    assert _run(backup_dir, write=write) == 0
    if not write:
        assert "DRY_RUN only" in capsys.readouterr().out
        assert offline_restore.instances == []
        assert offline_restore.settings_calls == []
        return

    sheet, = offline_restore.instances
    growth = {}
    if rows < 1201:
        growth["rowCount"] = 1201
    if columns < 40:
        growth["columnCount"] = 40
    if growth:
        request, = _metadata_requests(sheet)
        update = request["updateSheetProperties"]
        assert update["properties"]["sheetId"] == 17
        assert update["properties"]["gridProperties"] == growth
        assert set(update["fields"].split(",")) == {f"gridProperties.{key}" for key in growth}
    else:
        assert not any(operation == "metadata" for operation, _payload in sheet.calls)

    clears = [payload for operation, payload in sheet.calls if operation == "clear"]
    updates = [payload for operation, payload in sheet.calls if operation == "update"]
    assert clears == [{"range": "'clients'!A1:ZZ"}]
    assert updates == [{"range": "'clients'!A1:AN1201", "valueInputOption": "RAW", "body": {"values": values}}]


@pytest.mark.parametrize("values", [[], [[]], [["small"]], _large_values()], ids=["empty", "empty-row", "small", "large"])
@pytest.mark.parametrize("write", [True, False], ids=["write", "dry-run"])
def test_missing_sheet_has_adequate_grid_before_clear(tmp_path, offline_restore, values, write):
    backup_dir = _write_backup(tmp_path, {"new tab": values})

    assert _run(backup_dir, write=write) == 0
    if not write:
        assert offline_restore.instances == []
        assert offline_restore.settings_calls == []
        return

    sheet, = offline_restore.instances
    request, = _metadata_requests(sheet)
    properties = request["addSheet"]["properties"]
    assert properties["title"] == "new tab"
    assert properties["gridProperties"]["rowCount"] >= max(len(values), 1)
    assert properties["gridProperties"]["columnCount"] >= max(max((len(row) for row in values), default=0), 1)
    assert [payload["range"] for operation, payload in sheet.calls if operation == "clear"] == ["'new tab'!A1:ZZ"]
    updates = [payload for operation, payload in sheet.calls if operation == "update"]
    assert len(updates) == bool(values)
    if values:
        assert updates[0]["body"] == {"values": values}


def test_all_tabs_prepared_in_one_metadata_batch_before_any_clear(tmp_path, offline_restore):
    tabs = {
        "already large": [["keep-capacity"]],
        "wide": [[f"column-{column}" for column in range(40)]],
        "tall": [["row"] for _ in range(1201)],
        "new wide and tall": _large_values(),
    }
    offline_restore.sheets = [
        _properties("already large", 1, 2000, 60),
        _properties("wide", 2, 1000, 26),
        _properties("tall", 3, 1000, 60),
        _properties("unrelated", 4, 3000, 80),
    ]
    backup_dir = _write_backup(tmp_path, tabs)

    assert _run(backup_dir) == 0
    sheet, = offline_restore.instances
    requests = _metadata_requests(sheet)
    updates = {request["updateSheetProperties"]["properties"]["sheetId"]: request["updateSheetProperties"]
               for request in requests if "updateSheetProperties" in request}
    additions = [request["addSheet"]["properties"] for request in requests if "addSheet" in request]
    assert len(requests) == 3
    assert set(updates) == {2, 3}
    assert updates[2]["properties"]["gridProperties"] == {"columnCount": 40}
    assert updates[3]["properties"]["gridProperties"] == {"rowCount": 1201}
    added, = additions
    assert added["title"] == "new wide and tall"
    assert added["gridProperties"]["rowCount"] >= 1201
    assert added["gridProperties"]["columnCount"] >= 40
    assert [payload["range"] for operation, payload in sheet.calls if operation == "clear"] == [
        f"'{title}'!A1:ZZ" for title in tabs
    ]
    assert [payload["body"]["values"] for operation, payload in sheet.calls if operation == "update"] == list(tabs.values())


@pytest.mark.parametrize("missing", [False, True], ids=["existing", "missing"])
def test_apostrophes_are_escaped_in_clear_and_update_ranges(tmp_path, offline_restore, missing):
    title = "Coach's 'week'"
    if not missing:
        offline_restore.sheets = [_properties(title, 8, 1000, 26)]
    values = [[f"column-{column}" for column in range(40)]]
    backup_dir = _write_backup(tmp_path, {title: values})

    assert _run(backup_dir) == 0
    sheet, = offline_restore.instances
    _metadata_requests(sheet)
    assert [(operation, payload["range"]) for operation, payload in sheet.calls if operation in {"clear", "update"}] == [
        ("clear", "'Coach''s ''week'''!A1:ZZ"),
        ("update", "'Coach''s ''week'''!A1:AN1"),
    ]


def test_metadata_failure_leaves_all_values_untouched(tmp_path, offline_restore):
    offline_restore.sheets = [
        _properties("already large", 1, 2000, 60),
        _properties("needs resize", 2, 1000, 26),
    ]
    offline_restore.fail_metadata = True
    backup_dir = _write_backup(tmp_path, {
        "already large": [["would otherwise be cleared first"]],
        "needs resize": _large_values(),
        "missing": [["new value"]],
    })

    with pytest.raises(RuntimeError, match="synthetic metadata resize failure"):
        _run(backup_dir)

    sheet, = offline_restore.instances
    assert [operation for operation, _payload in sheet.calls] == ["get", "metadata"]
    assert sheet.stored_values == {
        "already large": [["original-value"]],
        "needs resize": [["original-value"]],
    }


@pytest.mark.parametrize("target", [*PROTECTED.values(), "", None], ids=["main-prod", "intake-prod", "empty", "omitted"])
def test_write_guard_refuses_before_google_or_credentials(tmp_path, offline_restore, target, capsys):
    backup_dir = _write_backup(tmp_path, {"clients": _large_values()})

    assert _run(backup_dir, target=target) != 0
    assert "RESTORE_REFUSED" in capsys.readouterr().err
    assert offline_restore.instances == []
    assert offline_restore.settings_calls == []


@pytest.mark.parametrize("target", [*PROTECTED.values(), "", None], ids=["main-prod", "intake-prod", "empty", "omitted"])
def test_dry_run_remains_offline_for_protected_or_absent_target(tmp_path, offline_restore, target, capsys):
    backup_dir = _write_backup(tmp_path, {"clients": _large_values(), "missing": []})

    assert _run(backup_dir, write=False, target=target) == 0
    output = capsys.readouterr().out
    assert "BACKUP_OK tabs=2" in output
    assert "DRY_RUN only" in output
    assert offline_restore.instances == []
    assert offline_restore.settings_calls == []
