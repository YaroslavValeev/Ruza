from __future__ import annotations

from datetime import date

from packages.sheets import SheetWrapper


def get_marketing_funnel(
    sheet: SheetWrapper,
    *,
    club_id: str,
    period_from: str,
    period_to: str,
) -> dict[str, int | float | str | None]:
    leads = [
        row
        for row in sheet.read_tab("leads")
        if row.get("club_id") == club_id
        and period_from <= row.get("created_at", "")[:10] <= period_to
    ]
    leads_count = len(leads)
    contacted_count = len([row for row in leads if row.get("status") == "contacted"])
    booked_count = len([row for row in leads if row.get("status") == "booked"])
    lost_count = len([row for row in leads if row.get("status") == "lost"])

    conversion = round((booked_count / leads_count) * 100, 2) if leads_count else 0.0

    campaigns = [row for row in sheet.read_tab("campaigns") if row.get("club_id") == club_id]
    total_budget = sum(int(row.get("budget") or 0) for row in campaigns)
    cac_estimate = int(total_budget / booked_count) if booked_count and total_budget else None

    return {
        "period_from": period_from,
        "period_to": period_to,
        "leads_count": leads_count,
        "contacted_count": contacted_count,
        "booked_count": booked_count,
        "lost_count": lost_count,
        "conversion_to_booked_pct": conversion,
        "cac_estimate": cac_estimate,
    }
