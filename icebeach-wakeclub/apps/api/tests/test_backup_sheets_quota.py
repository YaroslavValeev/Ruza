from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httplib2
import pytest
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("backup_sheets", ROOT / "scripts" / "backup_sheets.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class Clock:
    now = 0.0

    def __init__(self):
        self.delays = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.delays.append(seconds)
        self.now += seconds


class Sheet:
    def _execute_with_retries(self, factory, *, attempts):
        assert attempts == 1
        return factory()


def http_error(status, **headers):
    return HttpError(httplib2.Response({"status": status, **headers}), b"private-details", uri="private-uri")


@pytest.fixture
def clock(monkeypatch):
    value = Clock()
    monkeypatch.setattr(backup, "time", value)
    monkeypatch.setattr(backup.random, "uniform", lambda *_: 0.5)
    return value


@pytest.mark.parametrize("error", [http_error(429), http_error(503), OSError("network")])
def test_transient_retry_then_success(clock, caplog, error):
    results = iter([error, {"values": []}])

    def request():
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    assert backup._BackupReader(Sheet()).read(request) == {"values": []}
    assert clock.now >= 2
    assert "private-details" not in caplog.text
    assert "private-uri" not in caplog.text


def test_read_requests_are_paced(clock):
    reader = backup._BackupReader(Sheet())
    starts = []
    for _ in range(3):
        reader.read(lambda: starts.append(clock.now))
    assert starts == [0, 2, 4]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_errors_are_not_retried(clock, status):
    calls = []

    def request():
        calls.append(1)
        raise http_error(status)

    with pytest.raises(HttpError):
        backup._BackupReader(Sheet()).read(request)
    assert len(calls) == 1
    assert clock.delays == []


@pytest.mark.parametrize("reason", ["rateLimitExceeded", "userRateLimitExceeded"])
def test_403_rate_limit_reasons_are_retried(clock, reason):
    calls = []

    def request():
        calls.append(1)
        if len(calls) == 1:
            payload = {"error": {"errors": [{"reason": reason}]}}
            raise HttpError(httplib2.Response({"status": 403}), json.dumps(payload).encode())
        return {}

    assert backup._BackupReader(Sheet()).read(request) == {}
    assert len(calls) == 2


@pytest.mark.parametrize("content", [b"not-json", b"[]", b'{"error": null}', b'{"error":{"errors":{}}}',
                                   b'{"error":{"errors":[{"reason":"forbidden"}]}}'])
def test_403_unknown_or_permission_reason_does_not_retry(clock, content):
    exc = HttpError(httplib2.Response({"status": 403}), content)
    assert backup._retryable_http_error(exc) is False


def test_retry_exhaustion_is_bounded_and_redacted(clock):
    calls = []

    def request():
        calls.append(1)
        raise http_error(429)

    with pytest.raises(RuntimeError, match="after 8 attempts") as exc:
        backup._BackupReader(Sheet()).read(request)
    assert len(calls) == 8
    assert "private" not in str(exc.value)
    assert clock.now >= 64


def test_numeric_retry_after_is_honored(clock):
    calls = []

    def request():
        calls.append(clock.now)
        if len(calls) == 1:
            raise http_error(429, **{"retry-after": "65"})
        return {}

    backup._BackupReader(Sheet()).read(request)
    assert calls == [0, 65]


@pytest.mark.parametrize("header,expected", [("999999", 300), ("invalid", 2)])
def test_retry_after_is_bounded_and_invalid_values_are_ignored(clock, header, expected):
    calls = []

    def request():
        calls.append(clock.now)
        if len(calls) == 1:
            raise http_error(429, **{"retry-after": header})
        return {}

    backup._BackupReader(Sheet()).read(request)
    assert calls == [0, expected]


def setup_main(monkeypatch, tmp_path, *, fail_values=False):
    calls = []

    class FakeSheet(Sheet):
        def __init__(self, *_args, **_kwargs):
            self.service = self

        def spreadsheets(self):
            return self

        def values(self):
            return self

        def get(self, **kwargs):
            calls.append(kwargs)
            if "range" not in kwargs:
                return {"sheets": [{"properties": {"title": "Coach's notes"}}]}
            if fail_values:
                raise http_error(429)
            return {"values": [["client_id"], ["test-client"]]}

    monkeypatch.setattr(backup, "SheetWrapper", FakeSheet)
    monkeypatch.setattr(backup, "get_settings", lambda: SimpleNamespace(
        spreadsheet_id="test-sheet", service_account_json_path=None, service_account_info={},
    ))
    monkeypatch.setattr(sys, "argv", ["backup_sheets.py", "--out-dir", str(tmp_path)])
    return calls


def test_complete_backup_has_compatible_manifest(clock, monkeypatch, tmp_path):
    calls = setup_main(monkeypatch, tmp_path)
    assert backup.main() == 0
    manifest_path, = tmp_path.glob("*/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tab, = manifest["tabs"]
    assert calls[1]["range"] == "'Coach''s notes'!A1:ZZ"
    assert tab["rows"] == 2
    assert tab["sha256"] == hashlib.sha256((manifest_path.parent / tab["file"]).read_bytes()).hexdigest()


def test_failed_backup_never_publishes_manifest(clock, monkeypatch, tmp_path):
    setup_main(monkeypatch, tmp_path, fail_values=True)
    with pytest.raises(RuntimeError, match="after 8 attempts"):
        backup.main()
    assert list(tmp_path.glob("*/manifest.json")) == []
