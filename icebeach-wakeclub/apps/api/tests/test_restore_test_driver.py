from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest


SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
PROTECTED = {"SPREADSHEET_ID": "synthetic-main", "INTAKE_SPREADSHEET_ID": "synthetic-intake"}
TARGET = "synthetic-restore-target"
TITLE = "Synthetic restore proof"
VALUES = {"clients": [["id", "name"], ["001", "Test"], ["002", ""]], "empty": []}


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(root, tabs, source_id=PROTECTED["SPREADSHEET_ID"]):
    (root / "tabs").mkdir(parents=True, exist_ok=True)
    manifest = {"spreadsheet_id": source_id, "tabs": []}
    for index, (name, values) in enumerate(tabs.items()):
        relative = f"tabs/{index}.json"
        path = root / relative
        path.write_text(json.dumps(values), encoding="utf-8")
        manifest["tabs"].append({
            "name": name,
            "file": relative,
            "rows": len(values),
            "columns": max(map(len, values), default=0),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture
def offline(monkeypatch, tmp_path):
    driver = _module("offline_restore_test_driver", "restore_test.py")
    guard = _module("offline_restore_test_guard", "restore_sheets_backup.py")
    state = SimpleNamespace(driver=driver, root=tmp_path, write_error=None)

    def no_network(*args, **kwargs):
        pytest.fail("Offline restore tests must never access the network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    # main changes the process umask; never leak that change into the test runner.
    monkeypatch.setattr(driver.os, "umask", Mock(return_value=0o022))
    sheets = ModuleType("packages.sheets")
    sheet = SimpleNamespace()
    sheet.service = SimpleNamespace(spreadsheets=Mock(return_value=SimpleNamespace(
        get=Mock(return_value={"properties": {"title": TITLE}, "sheets": []}),
    )))
    sheet._execute_with_retries = lambda factory: factory()
    sheets.SheetWrapper = Mock(return_value=sheet)
    state.original_wrapper = sheets.SheetWrapper
    state.sheets = sheets
    state.metadata_get = sheet.service.spreadsheets.return_value.get
    import packages

    monkeypatch.setitem(sys.modules, "packages.sheets", sheets)
    monkeypatch.setattr(packages, "sheets", sheets)
    config = ModuleType("apps.api.app.config")
    config.get_settings = Mock(return_value=SimpleNamespace(
        spreadsheet_id=PROTECTED["SPREADSHEET_ID"],
        service_account_json_path="offline-unused.json",
        service_account_info=None,
    ))
    monkeypatch.setitem(sys.modules, "apps.api.app.config", config)

    def restore_main(argv):
        if "--write" in argv:
            assert sheets.SheetWrapper is not state.original_wrapper
            wrapped = sheets.SheetWrapper(TARGET, "offline-unused.json", service_account_info=None)
            assert wrapped._execute_with_retries(lambda: "offline-write", retries=1) == "offline-write"
            if state.write_error:
                raise state.write_error
        return 0

    state.restore = SimpleNamespace(
        check_write_target=Mock(wraps=guard.check_write_target),
        _load_protected_from_app_settings=Mock(return_value=PROTECTED),
        main=Mock(side_effect=restore_main),
    )

    def backup_main():
        args = sys.argv
        assert args[:3] == ["backup_sheets.py", "--spreadsheet-id", TARGET]
        assert args[3] == "--out-dir"
        _snapshot(Path(args[4]) / "synthetic-snapshot", VALUES, TARGET)
        return 0

    def reader(executor):
        return SimpleNamespace(read=Mock(side_effect=executor._execute_with_retries))

    state.backup = SimpleNamespace(main=Mock(side_effect=backup_main), _BackupReader=Mock(side_effect=reader))
    modules = {"restore_proof_helper": state.restore, "quota_backup_helper": state.backup}

    def load(name, path):
        assert path == tmp_path / {"restore_proof_helper": "restore_sheets_backup.py",
                                   "quota_backup_helper": "backup_sheets.py"}[name]
        return modules[name]

    monkeypatch.setattr(driver, "_load", Mock(side_effect=load))
    _snapshot(tmp_path / "source", VALUES)
    _snapshot(tmp_path / "before" / "synthetic-snapshot", {"previous": [["old"]]}, TARGET)
    state.marker = tmp_path / "snapshot-persisted"

    def run(phase, target=TARGET):
        return driver.main(["--phase", phase, "--work-dir", str(tmp_path),
                            "--target-spreadsheet-id", target, "--expected-target-title", TITLE])

    state.run = run
    return state


def test_compare_exact_values_and_cell_count(offline):
    actual = _snapshot(offline.root / "actual", dict(reversed(list(VALUES.items()))), TARGET)
    assert offline.driver._compare(offline.root / "source", actual) == {"status": "PASS", "tabs": 2, "cells": 6}


@pytest.mark.parametrize(("tabs", "message"), [
    ({"clients": VALUES["clients"]}, "a tab is missing"),
    ({**VALUES, "clients": [["id", "name"], ["001", "Changed"], ["002", ""]]}, "cell values differ"),
    ({**VALUES, "clients": [["id", "name"], [1, "Test"], ["002", ""]]}, "cell values differ"),
    ({**VALUES, "clients": [["id", "name"], ["001", "Test"], ["002"]]}, "cell values differ"),
])
def test_compare_rejects_missing_tab_or_differing_cells(offline, tabs, message):
    actual = _snapshot(offline.root / "actual", tabs, TARGET)
    with pytest.raises(RuntimeError, match=message):
        offline.driver._compare(offline.root / "source", actual)


def test_compare_rejects_empty_source(offline):
    source = _snapshot(offline.root / "empty-source", {})
    with pytest.raises(RuntimeError, match="Empty source backup"):
        offline.driver._compare(source, offline.root / "source")


@pytest.mark.parametrize(("expected", "actual"), [(1, True), (0, False)])
def test_compare_does_not_equate_numbers_with_booleans(offline, expected, actual):
    source = _snapshot(offline.root / "numeric-source", {"values": [[expected]]})
    restored = _snapshot(offline.root / "boolean-target", {"values": [[actual]]}, TARGET)
    with pytest.raises(RuntimeError, match="cell values differ"):
        offline.driver._compare(source, restored)


@pytest.mark.parametrize("phase", ["before", "restore", "after"])
@pytest.mark.parametrize("target", list(PROTECTED.values()))
def test_production_target_refused_before_wrapper_or_backup(offline, phase, target):
    with pytest.raises(RuntimeError, match="production"):
        offline.run(phase, target)
    offline.restore.check_write_target.assert_called_once_with(target, PROTECTED)
    offline.driver._load.assert_called_once()
    offline.original_wrapper.assert_not_called()
    offline.restore.main.assert_not_called()
    offline.backup.main.assert_not_called()


@pytest.mark.parametrize("phase", ["before", "restore", "after"])
def test_wrong_source_refused_before_target_access(offline, phase):
    _snapshot(offline.root / "source", VALUES, "synthetic-wrong-source")
    with pytest.raises(RuntimeError, match="Source must be the operational backup"):
        offline.run(phase)
    offline.original_wrapper.assert_not_called()
    offline.metadata_get.assert_not_called()
    offline.restore.main.assert_not_called()
    offline.backup.main.assert_not_called()


@pytest.mark.parametrize("phase", ["restore", "after"])
@pytest.mark.parametrize("marker_is_directory", [False, True])
def test_persisted_host_marker_required_before_write_or_backup(offline, phase, marker_is_directory):
    if marker_is_directory:
        offline.marker.mkdir()
    with pytest.raises(RuntimeError, match="pre-test snapshot on the host first"):
        offline.run(phase)
    assert all("--write" not in args[0] for args, _ in offline.restore.main.call_args_list)
    offline.backup.main.assert_not_called()
    assert offline.sheets.SheetWrapper is offline.original_wrapper


@pytest.mark.parametrize("phase", ["before", "restore", "after"])
def test_wrong_target_title_blocks_write_and_backup(offline, phase):
    offline.marker.touch()
    offline.metadata_get.return_value["properties"]["title"] = "Unexpected synthetic target"
    with pytest.raises(RuntimeError, match="Unexpected test target title"):
        offline.run(phase)
    assert all("--write" not in args[0] for args, _ in offline.restore.main.call_args_list)
    offline.backup.main.assert_not_called()
    assert not (offline.root / "target-metadata-before.json").exists()


@pytest.mark.parametrize("fail_write", [False, True])
def test_restore_calls_guard_and_helper_and_always_resets_wrapper(offline, fail_write):
    offline.marker.touch()
    if fail_write:
        offline.write_error = RuntimeError("synthetic write failure")
        with pytest.raises(RuntimeError, match="synthetic write failure"):
            offline.run("restore")
    else:
        assert offline.run("restore") == 0
    offline.restore.check_write_target.assert_called_once_with(TARGET, PROTECTED)
    assert offline.restore.main.call_args_list == [
        call(["--backup-dir", str(offline.root / "source")]),
        call(["--backup-dir", str(offline.root / "before" / "synthetic-snapshot")]),
        call(["--backup-dir", str(offline.root / "source"), "--write", "--target-spreadsheet-id", TARGET]),
    ]
    assert offline.sheets.SheetWrapper is offline.original_wrapper
    assert offline.backup._BackupReader.call_count == 2
    offline.backup.main.assert_not_called()


@pytest.mark.parametrize("phase", ["before", "after"])
def test_backup_failure_restores_sys_argv(offline, monkeypatch, phase):
    offline.marker.touch()
    previous = ["synthetic-caller", "--untouched"]
    monkeypatch.setattr(sys, "argv", previous)
    offline.backup.main.side_effect = RuntimeError("synthetic backup failure")
    with pytest.raises(RuntimeError, match="synthetic backup failure"):
        offline.run(phase)
    assert sys.argv is previous
    assert sys.argv == ["synthetic-caller", "--untouched"]
    assert offline.sheets.SheetWrapper is offline.original_wrapper
    assert not (offline.root / "proof.json").exists()


@pytest.mark.parametrize("phase", ["before", "after"])
def test_backup_phase_succeeds_and_after_persists_proof(offline, monkeypatch, capsys, phase):
    if phase == "after":
        offline.marker.touch()
    previous = ["synthetic-caller"]
    monkeypatch.setattr(sys, "argv", previous)
    assert offline.run(phase) == 0
    assert sys.argv is previous
    offline.backup.main.assert_called_once_with()
    assert all("--write" not in args[0] for args, _ in offline.restore.main.call_args_list)
    if phase == "after":
        proof = json.loads((offline.root / "proof.json").read_text(encoding="utf-8"))
        assert {key: proof[key] for key in ("status", "tabs", "cells")} == {"status": "PASS", "tabs": 2, "cells": 6}
        assert proof["verified_at"]
        assert "RESTORE_WRITE_READBACK_PASS tabs=2 cells=6" in capsys.readouterr().out
    else:
        metadata = json.loads((offline.root / "target-metadata-before.json").read_text(encoding="utf-8"))
        assert metadata["properties"]["title"] == TITLE
        assert not offline.marker.exists()
