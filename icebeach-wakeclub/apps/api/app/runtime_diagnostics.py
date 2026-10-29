from __future__ import annotations

import gc
import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


LOGGER = logging.getLogger("uvicorn.error")
_STATUS_FIELDS = {
    "VmRSS": "rss_kib",
    "VmHWM": "rss_high_water_kib",
    "RssAnon": "rss_anon_kib",
    "RssFile": "rss_file_kib",
    "RssShmem": "rss_shared_kib",
    "VmSwap": "swap_kib",
    "Threads": "threads",
}


def runtime_memory_diagnostics_enabled() -> bool:
    return os.getenv("RUNTIME_MEMORY_DIAGNOSTICS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def process_memory_snapshot(proc_root: Path = Path("/proc/self")) -> dict[str, int | list[int]]:
    """Return bounded process metrics without adding a runtime dependency."""
    snapshot: dict[str, int | list[int]] = {}
    try:
        for line in (proc_root / "status").read_text(encoding="utf-8").splitlines():
            name, separator, raw_value = line.partition(":")
            target = _STATUS_FIELDS.get(name)
            if not separator or target is None:
                continue
            value = raw_value.strip().split(maxsplit=1)[0]
            snapshot[target] = int(value)
    except (OSError, ValueError):
        pass

    try:
        snapshot["open_fds"] = sum(1 for _ in (proc_root / "fd").iterdir())
    except OSError:
        pass

    snapshot["gc_counts"] = list(gc.get_count())
    return snapshot


def _sheet_snapshot(sheet: object) -> dict[str, int]:
    snapshot = getattr(sheet, "diagnostics_snapshot", None)
    if not callable(snapshot):
        return {}
    try:
        result = snapshot()
    except Exception:
        LOGGER.warning("RUNTIME_MEMORY_DIAGNOSTIC sheet_snapshot_failed", exc_info=False)
        return {}
    if not isinstance(result, dict):
        return {}
    return {
        str(key): int(value)
        for key, value in result.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }


def _numeric_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, int]:
    return {
        key: int(value) - int(before.get(key, 0))
        for key, value in after.items()
        if isinstance(value, int)
        and not isinstance(value, bool)
        and isinstance(before.get(key, 0), int)
        and not isinstance(before.get(key, 0), bool)
    }


@contextmanager
def observe_runtime_operation(operation: str, sheet: object) -> Iterator[None]:
    """Log one structured, content-free diagnostic event for an operation."""
    if not runtime_memory_diagnostics_enabled():
        yield
        return

    started = time.monotonic()
    process_before = process_memory_snapshot()
    sheet_before = _sheet_snapshot(sheet)
    success = False
    error_type = ""
    try:
        yield
        success = True
    except Exception as exc:
        error_type = type(exc).__name__
        raise
    finally:
        process_after = process_memory_snapshot()
        sheet_after = _sheet_snapshot(sheet)
        payload = {
            "event": "runtime_memory_diagnostic",
            "operation": operation,
            "success": success,
            "error_type": error_type,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "process_before": process_before,
            "process_after": process_after,
            "process_delta": _numeric_delta(process_before, process_after),
            "sheets_before": sheet_before,
            "sheets_after": sheet_after,
            "sheets_delta": _numeric_delta(sheet_before, sheet_after),
        }
        LOGGER.info(
            "RUNTIME_MEMORY_DIAGNOSTIC %s",
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        )
