from __future__ import annotations

import hashlib
from calendar import monthrange
from datetime import datetime, timedelta

from packages.sheets import SheetsSchemaError

from .errors import ApiError

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "schedule": ["weekday", "time", "boat_id", "capacity", "is_active"],
    "bookings": ["booking_id", "date", "time", "boat_id", "client_id", "status"],
    "slot_overrides": ["date", "time", "boat_id", "status"],
    "checkins": ["checkin_id", "booking_id", "status", "method"],
}

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"checked_in", "cancelled", "no_show"},
    "checked_in": {"in_progress", "cancelled", "no_show"},
    "in_progress": {"done", "no_show"},
    "done": set(),
    "cancelled": set(),
    "no_show": set(),
}

ROLE_ALLOWED_TRANSITIONS: dict[str, set[tuple[str, str]]] = {
    "pilot": {
        ("checked_in", "in_progress"),
        ("in_progress", "done"),
        ("in_progress", "no_show"),
    },
    "operator": {
        ("confirmed", "cancelled"),
        ("confirmed", "no_show"),
        ("confirmed", "checked_in"),
        ("checked_in", "cancelled"),
    },
    "admin": set(),  # admin may do all valid transitions
}


def normalize_hhmm(raw_value: str) -> str:
    return datetime.strptime(raw_value, "%H:%M").strftime("%H:%M")


def weekday_name(date_iso: str) -> str:
    return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%A").lower()


def booking_id_for(request: dict, club_id: str = "ice_beach_ruza") -> str:
    payload = (
        f"{club_id}|{request['client_id']}|{request['date']}|{request['time']}|{request['boat_id']}|"
        f"{int(bool(request.get('coach_required')))}|{request.get('coach_user_id') or ''}"
    )
    digest = hashlib.sha1(payload.encode()).hexdigest()[:16]
    return f"bk_{digest}"


def _validate_schema_or_raise(sheets) -> None:
    for tab, required in REQUIRED_COLUMNS.items():
        missing = sheets.validate_required_columns(tab, required)
        if missing:
            raise ApiError(
                status_code=400,
                code="COLUMN_MISSING",
                message=f"Missing columns in '{tab}': {', '.join(missing)}",
            )


def build_availability(sheets, date_iso: str, club_id: str = "ice_beach_ruza") -> list[dict]:
    try:
        _validate_schema_or_raise(sheets)
        weekday = weekday_name(date_iso)
        schedule_rows = sheets.find(
            "schedule",
            lambda row: row.get("weekday", "").lower() == weekday
            and row.get("is_active", "").lower() in {"true", "1", "yes"}
            and (not row.get("club_id") or row.get("club_id") == club_id),
        )
        overrides = sheets.find(
            "slot_overrides",
            lambda row: row.get("date") == date_iso
            and (not row.get("club_id") or row.get("club_id") == club_id),
        )
        bookings = sheets.find(
            "bookings",
            lambda row: row.get("date") == date_iso and row.get("status", "") != "cancelled",
        )
    except SheetsSchemaError as exc:
        raise ApiError(status_code=400, code=exc.code, message=str(exc)) from exc
    except ValueError as exc:
        raise ApiError(status_code=400, code="INVALID_DATE", message=str(exc)) from exc

    override_map: dict[tuple[str, str], dict] = {}
    for row in overrides:
        override_map[(row.get("time", ""), row.get("boat_id", ""))] = row

    booked_map: dict[tuple[str, str], int] = {}
    for row in bookings:
        key = (row.get("time", ""), row.get("boat_id", ""))
        booked_map[key] = booked_map.get(key, 0) + 1

    result: list[dict] = []
    for row in schedule_rows:
        time_value = normalize_hhmm(row.get("time", ""))
        boat_id = row.get("boat_id", "")
        capacity = int(row.get("capacity", 0) or 0)
        status = "active"
        override = override_map.get((time_value, boat_id))
        if override:
            status = override.get("status", "active")
            if override.get("capacity"):
                capacity = int(override["capacity"])
        booked_count = booked_map.get((time_value, boat_id), 0)
        remaining = max(0, capacity - booked_count)
        result.append(
            {
                "date": date_iso,
                "time": time_value,
                "boat_id": boat_id,
                "capacity": capacity,
                "booked_count": booked_count,
                "remaining": remaining,
                "status": status,
            }
        )
    return result


def create_booking(sheets, request: dict, actor: str) -> dict:
    try:
        _validate_schema_or_raise(sheets)
        normalize_hhmm(request["time"])
        datetime.strptime(request["date"], "%Y-%m-%d")
    except ValueError as exc:
        raise ApiError(status_code=400, code="INVALID_DATE", message=str(exc)) from exc
    except SheetsSchemaError as exc:
        raise ApiError(status_code=400, code=exc.code, message=str(exc)) from exc

    booking_id = booking_id_for(request)
    existing = sheets.find("bookings", lambda row: row.get("booking_id") == booking_id)
    if existing:
        return {
            "booking_id": booking_id,
            "status": existing[0].get("status", "confirmed"),
            "total_price": float(existing[0].get("total_price") or 0),
            "idempotent_replay": True,
        }

    slots = build_availability(sheets, request["date"])
    matched = [
        s for s in slots if s["time"] == normalize_hhmm(request["time"]) and s["boat_id"] == request["boat_id"]
    ]
    if not matched or matched[0]["status"] in {"closed", "private"}:
        raise ApiError(status_code=409, code="SLOT_FULL", message="Slot unavailable")
    if matched[0]["remaining"] <= 0:
        raise ApiError(status_code=409, code="SLOT_FULL", message="Slot capacity is full")

    total_price = float(request["price_base"]) + float(request["price_coach"])
    payload = {
        "booking_id": booking_id,
        "client_id": request["client_id"],
        "date": request["date"],
        "time": normalize_hhmm(request["time"]),
        "boat_id": request["boat_id"],
        "coach_required": str(bool(request.get("coach_required"))).upper(),
        "coach_user_id": request.get("coach_user_id") or "",
        "price_base": request["price_base"],
        "price_coach": request["price_coach"],
        "total_price": total_price,
        "status": "confirmed",
    }
    sheets.append_row("bookings", payload)
    sheets.write_audit(
        action="create",
        entity="booking",
        entity_id=booking_id,
        diff_json=payload,
        actor=actor,
    )
    return {
        "booking_id": booking_id,
        "status": "confirmed",
        "total_price": total_price,
        "idempotent_replay": False,
    }


def create_checkin(sheets, booking_id: str, method: str, status: str, actor: str) -> dict:
    _validate_schema_or_raise(sheets)
    allowed_statuses = {"arrived", "ready", "late"}
    allowed_methods = {"phone", "manual"}
    if status not in allowed_statuses:
        raise ApiError(status_code=400, code="INVALID_STATUS", message="Invalid checkin status")
    if method not in allowed_methods:
        raise ApiError(status_code=400, code="INVALID_STATUS", message="Invalid checkin method")

    booking_rows = sheets.find("bookings", lambda row: row.get("booking_id") == booking_id)
    if not booking_rows:
        raise ApiError(status_code=404, code="BOOKING_NOT_FOUND", message="Booking not found")

    existing = sheets.find(
        "checkins",
        lambda row: row.get("booking_id") == booking_id
        and row.get("status") == status
        and row.get("method") == method,
    )
    if existing:
        return {
            "checkin_id": existing[0].get("checkin_id", ""),
            "booking_id": booking_id,
            "status": status,
            "method": method,
            "idempotent_replay": True,
        }

    checkin_id = f"chk_{hashlib.sha1(f'{booking_id}|{status}|{method}'.encode()).hexdigest()[:12]}"
    checkin_payload = {
        "checkin_id": checkin_id,
        "booking_id": booking_id,
        "status": status,
        "method": method,
        "created_by": actor,
    }
    sheets.append_row("checkins", checkin_payload)

    booking_status = "checked_in" if status in {"arrived", "ready"} else booking_rows[0].get("status", "confirmed")
    sheets.update_by_id("bookings", "booking_id", booking_id, {"status": booking_status})

    sheets.write_audit(
        action="create",
        entity="checkin",
        entity_id=checkin_id,
        diff_json=checkin_payload,
        actor=actor,
    )
    sheets.write_audit(
        action="update",
        entity="booking",
        entity_id=booking_id,
        diff_json={"status": booking_status, "ready_state": status},
        actor=actor,
    )
    return {
        "checkin_id": checkin_id,
        "booking_id": booking_id,
        "status": status,
        "method": method,
        "idempotent_replay": False,
    }


def get_pilot_queue(sheets, date_iso: str, boat_id: str) -> list[dict]:
    _validate_schema_or_raise(sheets)
    datetime.strptime(date_iso, "%Y-%m-%d")

    bookings = sheets.find(
        "bookings",
        lambda row: row.get("date") == date_iso and row.get("boat_id") == boat_id and row.get("status") != "cancelled",
    )
    checkins = sheets.find("checkins", lambda row: True)

    ready_map: dict[str, str] = {}
    for row in checkins:
        bid = row.get("booking_id", "")
        if bid:
            ready_map[bid] = row.get("status", "")

    def masked(client: str) -> str:
        if len(client) < 4:
            return "***"
        return f"{client[:2]}***{client[-2:]}"

    queue = []
    for row in bookings:
        queue.append(
            {
                "booking_id": row.get("booking_id", ""),
                "time": normalize_hhmm(row.get("time", "00:00")),
                "client": masked(row.get("client_id", "unknown")),
                "status": row.get("status", "confirmed"),
                "ready_state": ready_map.get(row.get("booking_id", ""), ""),
                "notes": row.get("notes", ""),
            }
        )

    return sorted(queue, key=lambda item: item["time"])


def update_booking_status(sheets, booking_id: str, new_status: str, actor: str, actor_role: str) -> dict:
    _validate_schema_or_raise(sheets)
    booking_rows = sheets.find("bookings", lambda row: row.get("booking_id") == booking_id)
    if not booking_rows:
        raise ApiError(status_code=404, code="BOOKING_NOT_FOUND", message="Booking not found")

    current_status = booking_rows[0].get("status", "confirmed")
    if new_status not in STATUS_TRANSITIONS.get(current_status, set()):
        raise ApiError(status_code=400, code="INVALID_STATUS", message="Invalid status transition")

    if actor_role != "admin":
        allowed = ROLE_ALLOWED_TRANSITIONS.get(actor_role, set())
        if (current_status, new_status) not in allowed:
            raise ApiError(status_code=403, code="FORBIDDEN", message="Role cannot perform this transition")

    sheets.update_by_id("bookings", "booking_id", booking_id, {"status": new_status})
    sheets.write_audit(
        action="update",
        entity="booking",
        entity_id=booking_id,
        diff_json={"from": current_status, "to": new_status},
        actor=actor,
    )
    return {"booking_id": booking_id, "status": new_status}


def _date_range(period: str, today_iso: str) -> list[str]:
    base = datetime.strptime(today_iso, "%Y-%m-%d")
    if period == "today":
        return [today_iso]
    if period == "week":
        start = base - timedelta(days=base.weekday())
        return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    if period == "month":
        start = base.replace(day=1)
        days = monthrange(start.year, start.month)[1]
        return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    raise ApiError(status_code=400, code="INVALID_DATE", message="Unknown KPI period")


def _safe_float(raw, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _compute_kpi_for_dates(sheets, dates: list[str]) -> dict:
    bookings = sheets.find("bookings", lambda row: row.get("date") in dates)
    done_like = [b for b in bookings if b.get("status") in {"done", "in_progress", "checked_in"}]
    no_show = [b for b in bookings if b.get("status") == "no_show"]
    coach = [b for b in bookings if str(b.get("coach_required", "")).lower() in {"true", "1"}]
    unique_clients = {b.get("client_id", "") for b in bookings if b.get("client_id")}

    capacity_total = 0
    for day in dates:
        try:
            weekday = weekday_name(day)
        except ValueError:
            continue
        schedule_rows = sheets.find(
            "schedule",
            lambda row: row.get("weekday", "").lower() == weekday
            and row.get("is_active", "").lower() in {"true", "1", "yes"},
        )
        capacity_total += sum(int(r.get("capacity", 0) or 0) for r in schedule_rows)

    utilization = (len(done_like) / capacity_total * 100) if capacity_total else 0.0
    revenue = sum(_safe_float(b.get("total_price")) for b in done_like)
    coach_attach = (len(coach) / len(bookings) * 100) if bookings else 0.0
    no_show_rate = (len(no_show) / len(bookings) * 100) if bookings else 0.0

    return {
        "utilization_pct": round(utilization, 2),
        "revenue_estimate": round(revenue, 2),
        "coach_attach_rate": round(coach_attach, 2),
        "no_show_rate": round(no_show_rate, 2),
        "new_clients_count": len(unique_clients),
        "bookings_count": len(bookings),
    }


def kpi_view(sheets, period: str, today_iso: str) -> dict:
    dates = _date_range(period=period, today_iso=today_iso)
    metrics = _compute_kpi_for_dates(sheets=sheets, dates=dates)
    if period == "today":
        upsert_analytics_daily(sheets=sheets, date_iso=today_iso, metrics=metrics, actor="system_kpi")
    return {
        "period": period,
        "from": dates[0],
        "to": dates[-1],
        "metrics": metrics,
    }


def kpi_drilldown(sheets, period: str, metric: str, today_iso: str) -> dict:
    dates = _date_range(period=period, today_iso=today_iso)
    bookings = sheets.find("bookings", lambda row: row.get("date") in dates)
    if metric == "revenue_estimate":
        rows = [b for b in bookings if b.get("status") in {"done", "in_progress", "checked_in"}]
    elif metric == "no_show_rate":
        rows = [b for b in bookings if b.get("status") == "no_show"]
    else:
        rows = bookings
    return {
        "period": period,
        "metric": metric,
        "count": len(rows),
        "bookings": rows[:100],
    }


def upsert_analytics_daily(sheets, date_iso: str, metrics: dict, actor: str) -> None:
    required = [
        "date",
        "utilization_pct",
        "revenue_estimate",
        "coach_attach_rate",
        "no_show_rate",
        "new_clients_count",
    ]
    missing = sheets.validate_required_columns("analytics_daily", required)
    if missing:
        raise ApiError(
            status_code=400,
            code="COLUMN_MISSING",
            message=f"Missing columns in 'analytics_daily': {', '.join(missing)}",
        )

    row = {"date": date_iso, **metrics}
    updated = sheets.update_by_id("analytics_daily", "date", date_iso, row)
    if not updated:
        sheets.append_row("analytics_daily", row)

    sheets.write_audit(
        action="update",
        entity="analytics_daily",
        entity_id=date_iso,
        diff_json=row,
        actor=actor,
    )


def diagnostics_snapshot(sheets, app_version: str, cache_ttl_seconds: int) -> dict:
    checks = {
        "staff_users": ["staff_user_id", "phone", "role"],
        "bookings": ["booking_id", "date", "time", "boat_id", "status"],
        "checkins": ["checkin_id", "booking_id", "status", "method"],
        "audit_log": ["ts", "actor", "action", "entity", "entity_id", "diff_json"],
        "analytics_daily": [
            "date",
            "utilization_pct",
            "revenue_estimate",
            "coach_attach_rate",
            "no_show_rate",
            "new_clients_count",
        ],
    }
    tab_status = {}
    warnings = []
    for tab, required in checks.items():
        missing = sheets.validate_required_columns(tab, required)
        tab_status[tab] = {"ok": len(missing) == 0, "missing": missing}
        if missing:
            warnings.append(f"{tab}: missing {', '.join(missing)}")
    return {
        "status": "ok" if not warnings else "warn",
        "app_version": app_version,
        "cache_ttl_seconds": cache_ttl_seconds,
        "tab_checks": tab_status,
        "warnings": warnings,
    }
