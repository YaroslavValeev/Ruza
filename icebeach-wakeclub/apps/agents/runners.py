from __future__ import annotations

from datetime import date

from .api_client import AgentsApiError, call_agents_api, call_health
from .config import AgentsSettings, get_agents_settings
from .notify import notify_all


def run_preflight_guard(settings: AgentsSettings | None = None) -> dict[str, object]:
    settings = settings or get_agents_settings()
    call_health(settings)
    today = date.today().isoformat()
    payload = call_agents_api(settings, "GET", "/internal/agents/preflight", query=f"date={today}")
    blockers = int(payload.get("blockers", 0))
    warnings = int(payload.get("warnings", 0))
    if blockers > 0:
        notify_all(settings, "Ops Alert: Preflight BLOCKER", f"Дата {today}. Blockers={blockers}, warnings={warnings}")
    elif warnings > 0:
        notify_all(settings, "Ops Alert: Preflight WARN", f"Дата {today}. Warnings={warnings}")
    return {"agent": "preflight_guard", "blockers": blockers, "warnings": warnings}


def run_late_marker(settings: AgentsSettings | None = None) -> dict[str, object]:
    settings = settings or get_agents_settings()
    hour = date.today().hour  # noqa: DTZ011 — local shift hours
    if hour < 8 or hour > 22:
        return {"agent": "late_marker", "skipped": True, "reason": "outside shift hours"}
    today = date.today().isoformat()
    payload = call_agents_api(settings, "POST", "/internal/agents/mark-late", query=f"date={today}&minutes_before=10")
    marked = int(payload.get("marked_late", 0))
    if marked > 0:
        notify_all(settings, "Late Marker", f"Отмечено опозданий: {marked} ({today})")
    return {"agent": "late_marker", "marked_late": marked}


def run_shift_snapshot(settings: AgentsSettings | None = None) -> dict[str, object]:
    settings = settings or get_agents_settings()
    today = date.today().isoformat()
    payload = call_agents_api(settings, "POST", "/internal/agents/snapshot", query=f"date={today}")
    notify_all(settings, "Shift Snapshot", f"analytics_daily записан за {today}. written={payload.get('written')}")
    return {"agent": "shift_snapshot", **payload}


def run_ops_alert(settings: AgentsSettings | None = None) -> dict[str, object]:
    settings = settings or get_agents_settings()
    try:
        health = call_health(settings)
        if health.get("status") != "ok":
            notify_all(settings, "Ops Alert", f"API health unexpected: {health}")
            return {"agent": "ops_alert", "healthy": False}
    except AgentsApiError as exc:
        notify_all(settings, "Ops Alert: API DOWN", str(exc))
        return {"agent": "ops_alert", "healthy": False, "error": str(exc)}

    today = date.today().isoformat()
    payload = call_agents_api(settings, "GET", "/internal/agents/preflight", query=f"date={today}")
    blockers = int(payload.get("blockers", 0))
    if blockers > 0:
        notify_all(settings, "Ops Alert", f"Preflight blockers={blockers} на {today}")
    return {"agent": "ops_alert", "healthy": True, "blockers": blockers}


def run_daily_brief(settings: AgentsSettings | None = None, *, mode: str = "morning") -> dict[str, object]:
    settings = settings or get_agents_settings()
    today = date.today().isoformat()
    payload = call_agents_api(settings, "GET", "/internal/agents/daily-brief", query=f"date={today}&mode={mode}")
    notify_all(settings, str(payload.get("title", "Daily Brief")), str(payload.get("text", "")))
    return {"agent": "daily_brief", "mode": mode, **payload}
