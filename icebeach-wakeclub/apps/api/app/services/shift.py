from __future__ import annotations

from packages.sheets import SheetWrapper

from .bookings import list_bookings
from .checkins import list_checkins


def get_shift_today(sheet: SheetWrapper, *, club_id: str, target_date: str) -> dict[str, object]:
    bookings = list_bookings(sheet, club_id=club_id, target_date=target_date)
    checkins = list_checkins(sheet, club_id=club_id, target_date=target_date)

    status_counts: dict[str, int] = {}
    for booking in bookings:
        status = str(booking.get("status", "confirmed"))
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "date": target_date,
        "bookings": bookings,
        "checkins": checkins,
        "summary": {
            "total_bookings": len(bookings),
            "checkins_count": len(checkins),
            "confirmed": status_counts.get("confirmed", 0),
            "arrived": status_counts.get("arrived", 0),
            "ready": status_counts.get("ready", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "done": status_counts.get("done", 0),
            "late": status_counts.get("late", 0),
            "no_show": status_counts.get("no_show", 0),
            "cancelled": status_counts.get("cancelled", 0),
        },
    }
