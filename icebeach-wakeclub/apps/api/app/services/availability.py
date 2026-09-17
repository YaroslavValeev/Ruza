from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from packages.sheets import SheetWrapper

from .common import parse_bool, weekday_iso0
from .operating_calendar import build_operating_slots, is_in_season, normalize_time_text


def get_availability_for_date(sheet: SheetWrapper, date_text: str, club_id: str) -> list[dict[str, Any]]:
    target_date = date.fromisoformat(date_text)
    if not is_in_season(target_date):
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
    for slot in build_operating_slots(boats, schedule_rows, weekday=weekday):
        slots[(slot["boat_id"], slot["time"])] = {"date": date_text, **slot}

    for row in override_rows:
        time_value = normalize_time_text(row.get("time"))
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
        key = (row.get("boat_id", ""), normalize_time_text(row.get("time")))
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
