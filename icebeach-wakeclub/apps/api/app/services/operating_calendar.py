from __future__ import annotations

from datetime import date
from typing import Any

from .common import parse_bool

SEASON_START_MONTH = 6
SEASON_START_DAY = 1
SEASON_END_MONTH = 10
SEASON_END_DAY = 1
OPEN_HOUR = 7
CLOSE_HOUR = 22
SLOT_MINUTES = 30


def is_in_season(target_date: date) -> bool:
    season_start = date(target_date.year, SEASON_START_MONTH, SEASON_START_DAY)
    season_end = date(target_date.year, SEASON_END_MONTH, SEASON_END_DAY)
    return season_start <= target_date <= season_end


def normalize_time_text(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or ":" not in raw:
        return raw
    hour_text, minute_text = raw.split(":", 1)
    if not hour_text.isdigit() or not minute_text.isdigit():
        return raw
    return f"{int(hour_text):02d}:{int(minute_text):02d}"


def generate_time_grid(start_time: str | None = None) -> list[str]:
    normalized_start = normalize_time_text(start_time) or f"{OPEN_HOUR:02d}:00"
    hour_text, minute_text = normalized_start.split(":", 1)
    minutes = max(int(hour_text) * 60 + int(minute_text), OPEN_HOUR * 60)
    last_start_minutes = CLOSE_HOUR * 60 - SLOT_MINUTES
    result: list[str] = []
    while minutes <= last_start_minutes:
        hour, minute = divmod(minutes, 60)
        result.append(f"{hour:02d}:{minute:02d}")
        minutes += SLOT_MINUTES
    return result


def build_operating_slots(
    boats: list[dict[str, str]],
    schedule_rows: list[dict[str, str]],
    *,
    weekday: int,
) -> list[dict[str, Any]]:
    active_boats = {
        row.get("boat_id", ""): row
        for row in boats
        if row.get("boat_id") and parse_bool(row.get("is_active"))
    }
    opening_rows: dict[str, dict[str, str]] = {}
    for row in schedule_rows:
        boat_id = row.get("boat_id", "")
        if (
            boat_id not in active_boats
            or not parse_bool(row.get("is_active"))
            or int(row.get("weekday") or -1) != weekday
        ):
            continue
        time_value = normalize_time_text(row.get("time"))
        if not time_value:
            continue
        current = opening_rows.get(boat_id)
        if current is None or time_value < normalize_time_text(current.get("time")):
            opening_rows[boat_id] = row

    result: list[dict[str, Any]] = []
    for boat_id, opening_row in opening_rows.items():
        boat = active_boats[boat_id]
        capacity = int(opening_row.get("capacity") or boat.get("capacity_default") or 1)
        for time_value in generate_time_grid(opening_row.get("time")):
            result.append(
                {
                    "time": time_value,
                    "boat_id": boat_id,
                    "capacity": capacity,
                    "status": "active",
                }
            )
    return sorted(result, key=lambda item: (item["time"], item["boat_id"]))
