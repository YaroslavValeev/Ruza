from __future__ import annotations

from packages.sheets import SheetWrapper

from .bookings import ACTIVE_BOOKING_STATUSES


def get_client_stats(sheet: SheetWrapper, *, club_id: str, client_id: str) -> dict[str, str | int]:
    clients = [row for row in sheet.read_tab("clients") if row.get("club_id") == club_id and row.get("client_id") == client_id]
    if not clients:
        return {}

    client = clients[0]
    bookings = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and row.get("client_id") == client_id
        and row.get("status") in ACTIVE_BOOKING_STATUSES | {"done"}
    ]

    sessions_count = len([row for row in bookings if row.get("status") == "done"])
    revenue_estimate = sum(int(row.get("total_price") or 0) for row in bookings if row.get("status") == "done")
    visit_dates = sorted({row.get("date", "") for row in bookings if row.get("date")})
    last_visit = visit_dates[-1] if visit_dates else ""

    return {
        "client_id": client_id,
        "full_name": client.get("full_name", ""),
        "phone": client.get("phone", ""),
        "consent_face": str(client.get("consent_face", "")).lower() in {"1", "true", "yes"},
        "consent_voice": str(client.get("consent_voice", "")).lower() in {"1", "true", "yes"},
        "sessions_count": sessions_count,
        "revenue_estimate": revenue_estimate,
        "visits_count": len(visit_dates),
        "last_visit_date": last_visit,
    }
