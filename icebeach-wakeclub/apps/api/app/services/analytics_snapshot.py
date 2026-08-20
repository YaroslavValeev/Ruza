from __future__ import annotations

from datetime import date

from packages.sheets import SheetWrapper

from .kpi import get_kpi_summary


def write_analytics_snapshot(sheet: SheetWrapper, *, club_id: str, target_date: str) -> dict[str, int | float | str | bool]:
    summary = get_kpi_summary(sheet, club_id, period="day", date_from=target_date, date_to=target_date)

    bookings = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id and row.get("date") == target_date
    ]
    eligible = [row for row in bookings if row.get("status") != "cancelled"]
    total_bookings = len(eligible)
    no_show_count = len([row for row in eligible if row.get("status") == "no_show"])
    no_show_rate = round((no_show_count / total_bookings) * 100, 2) if total_bookings else 0.0

    row = {
        "date": target_date,
        "club_id": club_id,
        "sessions_count": str(summary["sessions_count"]),
        "utilization_pct": str(summary["utilization_pct"]),
        "revenue_estimate": str(summary["revenue_estimate"]),
        "no_show_rate": str(no_show_rate),
        "notes": "snapshot",
    }

    existing = sheet.find("analytics_daily", {"date": target_date, "club_id": club_id})
    written = False
    if existing:
        sheet.update_by_id(
            "analytics_daily",
            "date",
            target_date,
            row,
            actor="system",
            audit_entity="analytics_daily",
        )
        written = True
    else:
        sheet.append_row("analytics_daily", row)
        written = True

    return {
        "date": target_date,
        "club_id": club_id,
        "sessions_count": int(summary["sessions_count"]),
        "utilization_pct": float(summary["utilization_pct"]),
        "revenue_estimate": int(summary["revenue_estimate"]),
        "no_show_rate": no_show_rate,
        "written": written,
    }
