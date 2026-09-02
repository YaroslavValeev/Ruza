from __future__ import annotations

from datetime import date

from packages.sheets import SheetWrapper

from .bookings import list_bookings
from .kpi import get_kpi_summary
from .shift import get_shift_today


def build_daily_brief(
    sheet: SheetWrapper,
    *,
    club_id: str,
    target_date: str,
    mode: str = "morning",
) -> dict[str, str | int | float | list | dict]:
    shift = get_shift_today(sheet, club_id=club_id, target_date=target_date)
    summary = shift["summary"]
    assert isinstance(summary, dict)

    kpi = get_kpi_summary(
        sheet,
        club_id,
        period="day",
        date_from=target_date,
        date_to=target_date,
    )

    bookings = shift["bookings"]
    assert isinstance(bookings, list)
    upcoming = [
        {
            "time": item.get("time", ""),
            "client_name": item.get("client_name", ""),
            "status": item.get("status", ""),
            "ride_type": item.get("ride_type", "wakeboard"),
        }
        for item in bookings
        if str(item.get("status", "")) not in {"done", "cancelled", "no_show"}
    ]
    upcoming.sort(key=lambda row: str(row.get("time", "")))

    if mode == "evening":
        title = f"Итоги смены {target_date}"
        lines = [
            f"Завершено: {summary.get('done', 0)}",
            f"Опоздания: {summary.get('late', 0)}",
            f"No-show: {summary.get('no_show', 0)}",
            f"Выручка (оценка): {kpi.get('revenue_estimate', 0)} ₽",
            f"Загрузка: {kpi.get('utilization_pct', 0)}%",
        ]
    else:
        title = f"План смены {target_date}"
        lines = [
            f"Броней: {summary.get('total_bookings', 0)}",
            f"Подтверждено: {summary.get('confirmed', 0)}",
            f"Уже на месте: {summary.get('arrived', 0) + int(summary.get('ready', 0))}",
            f"Загрузка (оценка): {kpi.get('utilization_pct', 0)}%",
        ]
        if upcoming:
            first = upcoming[0]
            lines.append(f"Ближайший: {first.get('time')} — {first.get('client_name')}")

    return {
        "mode": mode,
        "date": target_date,
        "club_id": club_id,
        "title": title,
        "text": "\n".join(lines),
        "summary": summary,
        "kpi": {
            "sessions_count": kpi.get("sessions_count", 0),
            "utilization_pct": kpi.get("utilization_pct", 0),
            "revenue_estimate": kpi.get("revenue_estimate", 0),
        },
        "upcoming": upcoming[:8],
    }


def format_brief_message(brief: dict[str, object]) -> str:
    title = str(brief.get("title", "Ice Beach Brief"))
    text = str(brief.get("text", ""))
    return f"{title}\n\n{text}"
