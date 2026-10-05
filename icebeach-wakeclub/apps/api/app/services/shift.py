from __future__ import annotations

from packages.sheets import SheetWrapper

from .bookings import list_bookings
from .checkins import list_checkins
from .ride_runtime import club_local_date


def club_timezone_name(sheet: SheetWrapper, club_id: str) -> str | None:
    row = next((item for item in sheet.read_tab("clubs") if item.get("club_id") == club_id), None)
    return (row or {}).get("timezone")


def club_local_today(sheet: SheetWrapper, club_id: str):
    return club_local_date(club_timezone_name(sheet, club_id))


def get_shift_today(
    sheet: SheetWrapper,
    *,
    club_id: str,
    target_date: str,
    coach_user_id: str | None = None,
) -> dict[str, object]:
    bookings = list_bookings(
        sheet,
        club_id=club_id,
        target_date=target_date,
        coach_user_id=coach_user_id,
    )
    checkins = list_checkins(sheet, club_id=club_id, target_date=target_date)
    if coach_user_id:
        allowed_ids = {str(booking.get("booking_id", "")) for booking in bookings}
        checkins = [item for item in checkins if str(item.get("booking_id") or "") in allowed_ids]

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
