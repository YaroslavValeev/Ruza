from __future__ import annotations

from datetime import date

from packages.sheets import SheetWrapper

from ..models import RideType
from .common import parse_bool

ACTIVE_PILOT_STATUSES = {"confirmed", "arrived", "ready", "in_progress", "late"}


def get_pilot_queue(
    sheet: SheetWrapper,
    boat_id: str,
    club_id: str,
    target_date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, str]]:
    if date_from and date_to:
        start_text = date_from
        end_text = date_to
    else:
        date_text = target_date or date.today().isoformat()
        start_text = date_text
        end_text = date_text

    clients = {row.get("client_id", ""): row for row in sheet.read_tab("clients") if row.get("club_id") == club_id}
    rows = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and start_text <= row.get("date", "") <= end_text
        and row.get("boat_id") == boat_id
        and row.get("status") in ACTIVE_PILOT_STATUSES
    ]
    rows.sort(key=lambda item: (item.get("date", ""), item.get("time", "")))

    return [
        {
            "booking_id": r.get("booking_id", ""),
            "date": r.get("date", ""),
            "time": r.get("time", ""),
            "boat_id": r.get("boat_id", ""),
            "client_id": r.get("client_id", ""),
            "client_name": clients.get(r.get("client_id", ""), {}).get("full_name", ""),
            "status": r.get("status", ""),
            "coach_required": parse_bool(r.get("coach_required")),
            "ride_type": r.get("ride_type") or "wakeboard",
        }
        for r in rows
    ]


def get_pilot_boat_id(sheet: SheetWrapper, *, staff_user_id: str, club_id: str) -> str | None:
    boats = [
        row
        for row in sheet.read_tab("boats")
        if row.get("club_id") == club_id
        and row.get("pilot_user_id") == staff_user_id
        and str(row.get("is_active", "")).lower() in {"1", "true", "yes"}
    ]
    if not boats:
        return None
    return boats[0].get("boat_id") or None
