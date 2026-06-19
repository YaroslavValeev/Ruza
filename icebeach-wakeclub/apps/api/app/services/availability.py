from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from packages.sheets import SheetWrapper

from .common import parse_bool, weekday_iso0

SEASON_START_MONTH = 6
SEASON_START_DAY = 1
SEASON_END_MONTH = 10
SEASON_END_DAY = 1
OPEN_HOUR = 7
CLOSE_HOUR = 22
SLOT_MINUTES = 30


def _is_in_season(target_date: date) -> bool:
    season_start = date(target_date.year, SEASON_START_MONTH, SEASON_START_DAY)
    season_end = date(target_date.year, SEASON_END_MONTH, SEASON_END_DAY)
    return season_start <= target_date <= season_end


def _generate_time_grid() -> list[str]:
    minutes = OPEN_HOUR * 60
    last_start_minutes = CLOSE_HOUR * 60 - SLOT_MINUTES
    result: list[str] = []
    while minutes <= last_start_minutes:
        hour, minute = divmod(minutes, 60)
        result.append(f"{hour:02d}:{minute:02d}")
        minutes += SLOT_MINUTES
    return result


def _normalize_time_text(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or ":" not in raw:
        return raw
    hour_text, minute_text = raw.split(":", 1)
    if not hour_text.isdigit() or not minute_text.isdigit():
        return raw
    return f"{int(hour_text):02d}:{int(minute_text):02d}"


def get_availability_for_date(sheet: SheetWrapper, date_text: str, club_id: str) -> list[dict[str, Any]]:
    target_date = date.fromisoformat(date_text)
    if not _is_in_season(target_date):
        return []

    weekday = weekday_iso0(date_text)
    boats = [
        row
        for row in sheet.read_tab("boats")
        if row.get("club_id") == club_id and parse_bool(row.get("is_active")) and row.get("boat_id")
    ]
    schedule_rows = [
        r
        for r in sheet.read_tab("schedule")
        if r.get("club_id") == club_id
        and parse_bool(r.get("is_active"))
        and int(r.get("weekday") or -1) == weekday
    ]
    override_rows = [
        r for r in sheet.read_tab("slot_overrides") if r.get("club_id") == club_id and r.get("date") == date_text
    ]
    booking_rows = [
        r
        for r in sheet.read_tab("bookings")
        if r.get("club_id") == club_id and r.get("date") == date_text and r.get("status") not in {"cancelled", "no_show"}
    ]

    slots: dict[tuple[str, str], dict[str, Any]] = {}
    time_grid = _generate_time_grid()

    for boat in boats:
        boat_id = boat.get("boat_id", "")
        if not boat_id:
            continue
        capacity = int(boat.get("capacity_default") or 1)
        for time_value in time_grid:
            key = (boat_id, time_value)
            slots[key] = {
                "date": date_text,
                "time": time_value,
                "boat_id": boat_id,
                "capacity": capacity,
                "status": "active",
            }

    for row in schedule_rows:
        time_value = _normalize_time_text(row.get("time"))
        key = (row.get("boat_id", ""), time_value)
        if not all(key):
            continue
        existing = slots.get(key)
        slots[key] = {
            "date": date_text,
            "time": time_value,
            "boat_id": row.get("boat_id", ""),
            "capacity": int(row.get("capacity") or (existing or {}).get("capacity", 0) or 0),
            "status": "active",
        }

    for row in override_rows:
        time_value = _normalize_time_text(row.get("time"))
        key = (row.get("boat_id", ""), time_value)
        if not all(key):
            continue
        slots[key] = {
            "date": date_text,
            "time": time_value,
            "boat_id": row.get("boat_id", ""),
            "capacity": int(row.get("capacity") or 0),
            "status": row.get("status", "active") or "active",
        }

    booking_counter: dict[tuple[str, str], int] = defaultdict(int)
    for row in booking_rows:
        key = (row.get("boat_id", ""), _normalize_time_text(row.get("time")))
        booking_counter[key] += 1

    result: list[dict[str, Any]] = []
    for (boat_id, time_value), slot in sorted(slots.items(), key=lambda item: (item[1]["time"], item[1]["boat_id"])):
        booked = booking_counter[(boat_id, time_value)]
        available = max(int(slot["capacity"]) - booked, 0)
        result.append(
            {
                "date": date_text,
                "time": time_value,
                "boat_id": boat_id,
                "capacity": int(slot["capacity"]),
                "booked": booked,
                "available": available,
                "status": slot["status"],
            }
        )

    return result
