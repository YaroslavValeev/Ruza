from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .common import parse_utc_instant

SET_DURATION_MINUTES = 25
SLOT_SPAN_MINUTES = 30
DEFAULT_CLUB_TIMEZONE = "Europe/Moscow"


def resolve_club_timezone(timezone_name: str | None) -> ZoneInfo:
    name = (timezone_name or "").strip() or DEFAULT_CLUB_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_CLUB_TIMEZONE)


def slot_start_local(date_text: str, time_text: str, zone: ZoneInfo) -> datetime:
    """Sheet slot date/time is club wall time, not UTC."""
    target = date.fromisoformat(date_text)
    hour_text, minute_text = (time_text or "00:00").split(":")[:2]
    return datetime.combine(target, time(hour=int(hour_text), minute=int(minute_text)), tzinfo=zone)


def parse_sets_count(row: dict[str, str]) -> int:
    value = int(row.get("sets_count") or 1)
    return max(value, 1)


def planned_duration_minutes(row: dict[str, str]) -> int:
    return parse_sets_count(row) * SET_DURATION_MINUTES


def parse_elapsed_seconds(row: dict[str, str]) -> int:
    return max(int(row.get("elapsed_seconds") or 0), 0)


def parse_actual_duration_seconds(row: dict[str, str]) -> int:
    return max(int(row.get("actual_duration_seconds") or 0), 0)


def timer_state(row: dict[str, str]) -> str:
    return row.get("timer_state", "idle") or "idle"


def _now(now: datetime | None = None) -> datetime:
    if now is not None:
        return now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def compute_elapsed_seconds(row: dict[str, str], *, now: datetime | None = None) -> int:
    elapsed = parse_elapsed_seconds(row)
    if timer_state(row) != "running":
        return elapsed
    anchor = parse_utc_instant(str(row.get("timer_anchor_at", "")))
    if anchor is None:
        return elapsed
    delta = int((_now(now) - anchor).total_seconds())
    return max(elapsed + max(delta, 0), 0)


def compute_remaining_seconds(row: dict[str, str], *, now: datetime | None = None) -> int:
    planned_seconds = planned_duration_minutes(row) * 60
    return max(planned_seconds - compute_elapsed_seconds(row, now=now), 0)


def offset_time_text(time_text: str, slot_offset: int) -> str:
    hour, minute = (int(part) for part in time_text.split(":"))
    base = datetime(2000, 1, 1, hour, minute, tzinfo=timezone.utc)
    shifted = base + timedelta(minutes=SLOT_SPAN_MINUTES * slot_offset)
    return shifted.strftime("%H:%M")


def iter_booking_slots(row: dict[str, str]) -> list[str]:
    return [offset_time_text(str(row.get("time", "00:00")), index) for index in range(parse_sets_count(row))]
