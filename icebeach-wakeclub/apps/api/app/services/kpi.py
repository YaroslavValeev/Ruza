from __future__ import annotations

from datetime import date, timedelta

from packages.sheets import SheetWrapper

from ..models import KpiPeriod, RideType


def _pct(actual: float | int, target: int | None) -> float | None:
    if not target:
        return None
    return round((float(actual) / target) * 100, 2)


def _get_kpi_targets(sheet: SheetWrapper, club_id: str, period: KpiPeriod, anchor: date) -> dict[str, int] | None:
    period_key = anchor.strftime("%Y-%m") if period in {"month", "season"} else anchor.strftime("%Y-W%W")
    rows = [
        row
        for row in sheet.read_tab("kpi_targets")
        if row.get("club_id") == club_id and row.get("period") == period_key
    ]
    if not rows:
        return None
    row = rows[0]
    return {
        "sessions_target": int(row.get("sessions_target") or 0),
        "utilization_target_pct": int(row.get("utilization_target_pct") or 0),
        "revenue_target": int(row.get("revenue_target") or 0),
    }

SEASON_START_MONTH = 6
SEASON_START_DAY = 1
SEASON_END_MONTH = 10
SEASON_END_DAY = 1


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _get_period_bounds(period: KpiPeriod, *, today: date, date_from: str | None, date_to: str | None) -> tuple[date, date]:
    if period == "day":
        target = _parse_date(date_from) if date_from else today
        return target, target

    if period == "week":
        anchor = _parse_date(date_from) if date_from else today
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        return start, end

    if period == "month":
        anchor = _parse_date(date_from) if date_from else today
        start = anchor.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        end = next_month - timedelta(days=1)
        return start, end

    if period == "season":
        anchor = _parse_date(date_from) if date_from else today
        year = anchor.year
        start = date(year, SEASON_START_MONTH, SEASON_START_DAY)
        end = date(year, SEASON_END_MONTH, SEASON_END_DAY)
        return start, end

    if period == "custom":
        if not date_from or not date_to:
            raise ValueError("date_from and date_to are required for custom KPI period")
        start = _parse_date(date_from)
        end = _parse_date(date_to)
        if end < start:
            raise ValueError("date_to must be greater than or equal to date_from")
        return start, end

    raise ValueError(f"Unsupported KPI period: {period}")


def _build_schedule_capacity_map(schedule_rows: list[dict[str, str]]) -> dict[int, int]:
    capacity_map: dict[int, int] = {weekday: 0 for weekday in range(7)}
    for row in schedule_rows:
        weekday = row.get("weekday", "")
        if weekday == "":
            continue
        capacity_map[int(weekday)] += int(row.get("capacity") or 0)
    return capacity_map


def get_kpi_summary(
    sheet: SheetWrapper,
    club_id: str,
    *,
    period: KpiPeriod = "day",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, int | float | str | list[dict[str, int | float | str]]]:
    today = date.today()
    start, end = _get_period_bounds(period, today=today, date_from=date_from, date_to=date_to)
    start_text = start.isoformat()
    end_text = end.isoformat()

    bookings = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and start_text <= row.get("date", "") <= end_text
        and row.get("status") == "done"
    ]

    schedule_rows = [
        row
        for row in sheet.read_tab("schedule")
        if row.get("club_id") == club_id and str(row.get("is_active", "")).lower() in {"1", "true", "yes"}
    ]
    schedule_capacity_map = _build_schedule_capacity_map(schedule_rows)

    sessions_count = len(bookings)
    revenue_estimate = sum(int(row.get("total_price") or 0) for row in bookings)

    ride_types: tuple[RideType, ...] = ("wakeboard", "surf", "skim")
    ride_breakdown_index = {
        ride_type: {
            "ride_type": ride_type,
            "sessions_count": 0,
            "revenue_estimate": 0,
        }
        for ride_type in ride_types
    }
    bookings_by_date: dict[str, list[dict[str, str]]] = {}

    for row in bookings:
        ride_type = str(row.get("ride_type") or "wakeboard")
        if ride_type not in ride_breakdown_index:
            ride_type = "wakeboard"
        ride_breakdown_index[ride_type]["sessions_count"] += 1
        ride_breakdown_index[ride_type]["revenue_estimate"] += int(row.get("total_price") or 0)
        bookings_by_date.setdefault(row.get("date", ""), []).append(row)

    if period == "day":
        capacity = schedule_capacity_map.get(start.weekday(), 0)
    else:
        capacity = 0
        total_days = (end - start).days + 1
        for offset in range(total_days):
            current_day = start + timedelta(days=offset)
            capacity += schedule_capacity_map.get(current_day.weekday(), 0)

    utilization_pct = round((sessions_count / capacity) * 100, 2) if capacity else 0

    timeline: list[dict[str, int | float | str]] = []
    total_days = (end - start).days + 1
    for offset in range(total_days):
        current_day = start + timedelta(days=offset)
        current_key = current_day.isoformat()
        day_bookings = bookings_by_date.get(current_key, [])
        day_sessions = len(day_bookings)
        day_revenue = sum(int(row.get("total_price") or 0) for row in day_bookings)
        day_capacity = schedule_capacity_map.get(current_day.weekday(), 0)
        day_utilization = round((day_sessions / day_capacity) * 100, 2) if day_capacity else 0
        timeline.append(
            {
                "date": current_key,
                "sessions_count": day_sessions,
                "revenue_estimate": day_revenue,
                "utilization_pct": day_utilization,
            }
        )

    return {
        "period": period,
        "date_from": start_text,
        "date_to": end_text,
        "sessions_count": sessions_count,
        "utilization_pct": utilization_pct,
        "revenue_estimate": revenue_estimate,
        "ride_breakdown": [ride_breakdown_index[ride_type] for ride_type in ride_types],
        "timeline": timeline,
        "plan_fact": _build_plan_fact(sheet, club_id, period, start, sessions_count, utilization_pct, revenue_estimate),
    }


def _build_plan_fact(
    sheet: SheetWrapper,
    club_id: str,
    period: KpiPeriod,
    anchor: date,
    sessions_count: int,
    utilization_pct: float,
    revenue_estimate: int,
) -> dict[str, int | float | None] | None:
    targets = _get_kpi_targets(sheet, club_id, period, anchor)
    if not targets:
        return None
    sessions_target = targets["sessions_target"] or None
    utilization_target = targets["utilization_target_pct"] or None
    revenue_target = targets["revenue_target"] or None
    return {
        "sessions_target": sessions_target,
        "utilization_target_pct": utilization_target,
        "revenue_target": revenue_target,
        "sessions_pct": _pct(sessions_count, sessions_target),
        "utilization_pct_of_target": _pct(utilization_pct, utilization_target),
        "revenue_pct": _pct(revenue_estimate, revenue_target),
    }
