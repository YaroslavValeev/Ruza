from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import pytest

from apps.api.app.runtime_diagnostics import observe_runtime_operation, process_memory_snapshot
from packages.sheets.sheet_wrapper import SheetWrapper


def test_process_memory_snapshot_reads_linux_proc_metrics(tmp_path: Path) -> None:
    (tmp_path / "status").write_text(
        "\n".join(
            (
                "VmRSS:\t101 kB",
                "VmHWM:\t202 kB",
                "RssAnon:\t77 kB",
                "RssFile:\t24 kB",
                "RssShmem:\t0 kB",
                "VmSwap:\t3 kB",
                "Threads:\t2",
            )
        ),
        encoding="utf-8",
    )
    fd_dir = tmp_path / "fd"
    fd_dir.mkdir()
    (fd_dir / "1").touch()
    (fd_dir / "2").touch()

    snapshot = process_memory_snapshot(tmp_path)

    assert snapshot == {
        "rss_kib": 101,
        "rss_high_water_kib": 202,
        "rss_anon_kib": 77,
        "rss_file_kib": 24,
        "rss_shared_kib": 0,
        "swap_kib": 3,
        "threads": 2,
        "open_fds": 2,
        "gc_counts": snapshot["gc_counts"],
    }
    assert len(snapshot["gc_counts"]) == 3


def test_observer_logs_bounded_aggregate_deltas(monkeypatch, caplog) -> None:
    monkeypatch.setenv("RUNTIME_MEMORY_DIAGNOSTICS_ENABLED", "true")

    class Sheet:
        calls = 0

        def diagnostics_snapshot(self) -> dict[str, int]:
            self.calls += 1
            return {"cache_hits": self.calls, "response_characters": self.calls * 10}

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with observe_runtime_operation("test.operation", Sheet()):
            pass

    record = next(record for record in caplog.records if record.message.startswith("RUNTIME_MEMORY_DIAGNOSTIC "))
    payload = json.loads(record.message.split(" ", 1)[1])
    assert payload["event"] == "runtime_memory_diagnostic"
    assert payload["operation"] == "test.operation"
    assert payload["success"] is True
    assert payload["error_type"] == ""
    assert payload["sheets_delta"] == {"cache_hits": 1, "response_characters": 10}
    assert "spreadsheet" not in record.message.lower()


def test_observer_is_silent_by_default(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with observe_runtime_operation("test.operation", object()):
            pass
    assert not [record for record in caplog.records if record.message.startswith("RUNTIME_MEMORY_DIAGNOSTIC ")]


def test_observer_logs_failure_type_without_exception_text(monkeypatch, caplog) -> None:
    monkeypatch.setenv("RUNTIME_MEMORY_DIAGNOSTICS_ENABLED", "true")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        with pytest.raises(RuntimeError, match="sensitive test detail"):
            with observe_runtime_operation("test.failure", object()):
                raise RuntimeError("sensitive test detail")

    record = next(record for record in caplog.records if record.message.startswith("RUNTIME_MEMORY_DIAGNOSTIC "))
    assert '"error_type":"RuntimeError"' in record.message
    assert "sensitive test detail" not in record.message


def test_sheet_wrapper_reports_cache_and_payload_aggregates() -> None:
    wrapper = SheetWrapper.__new__(SheetWrapper)
    wrapper._http_lock = threading.RLock()  # noqa: SLF001
    wrapper._diagnostics_enabled = True  # noqa: SLF001
    wrapper._diagnostic_counters = {}  # noqa: SLF001
    wrapper._tab_cache_ttl_seconds = 15  # noqa: SLF001
    wrapper._tab_cache = {}  # noqa: SLF001
    wrapper._execute_with_retries = lambda _factory: {  # type: ignore[method-assign]  # noqa: SLF001
        "values": [["id", "name"], ["1", "Alice"]]
    }

    assert wrapper._fetch_values("clients") == [["id", "name"], ["1", "Alice"]]  # noqa: SLF001
    assert wrapper._fetch_values("clients") == [["id", "name"], ["1", "Alice"]]  # noqa: SLF001

    assert wrapper.diagnostics_snapshot() == {
        "cache_misses": 1,
        "response_rows": 2,
        "response_cells": 4,
        "response_characters": 12,
        "cache_hits": 1,
        "tab_cache_entries": 1,
        "tab_cache_rows": 2,
        "tab_cache_cells": 4,
        "missing_tab_entries": 0,
    }
