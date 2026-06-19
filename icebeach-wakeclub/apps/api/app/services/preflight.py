from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from packages.sheets import SheetWrapper
from packages.sheets.schema import validate_required_columns

from .availability import get_availability_for_date
from .common import weekday_iso0

CRITICAL_TABS = (
    "staff_users",
    "boats",
    "clients",
    "pricing",
    "schedule",
    "slot_overrides",
    "bookings",
    "analytics_daily",
    "auth_codes",
    "audit_log",
)
REQUIRED_STAFF_ROLES = ("admin", "operator", "pilot")
ACTIVE_TRUE_VALUES = {"1", "true", "yes"}


@dataclass
class CheckItem:
    level: str
    code: str
    message: str


def _add(results: list[CheckItem], level: str, code: str, message: str) -> None:
    results.append(CheckItem(level=level, code=code, message=message))


def _is_active(value: str | None) -> bool:
    return str(value or "").strip().lower() in ACTIVE_TRUE_VALUES


def _fetch_headers(sheet: SheetWrapper, tab_name: str) -> list[str]:
    values = sheet._fetch_values(tab_name)  # noqa: SLF001
    if not values:
        raise ValueError(f"Tab '{tab_name}' is empty or missing header row")
    headers = values[0]
    validate_required_columns(tab_name, headers)
    return headers


def _detect_duplicates(rows: Iterable[dict[str, str]], key: str) -> list[str]:
    counts = Counter(row.get(key, "") for row in rows if row.get(key))
    return sorted(item for item, count in counts.items() if count > 1)


def run_preflight_check(sheet: SheetWrapper, *, target_date: str) -> dict[str, object]:
    results: list[CheckItem] = []

    for tab_name in CRITICAL_TABS:
        try:
            headers = _fetch_headers(sheet, tab_name)
            _add(results, "PASS", f"tab:{tab_name}", f"tab OK, columns={len(headers)}")
        except Exception as exc:
            _add(results, "BLOCKER", f"tab:{tab_name}", str(exc))

    blockers = [item for item in results if item.level == "BLOCKER"]
    if blockers:
        return {
            "target_date": target_date,
            "blockers": len(blockers),
            "warnings": 0,
            "checks": [item.__dict__ for item in results],
        }

    staff_rows = sheet.read_tab("staff_users")
    active_staff = [row for row in staff_rows if _is_active(row.get("is_active"))]
    active_roles = {row.get("role", "") for row in active_staff}
    active_club_ids = sorted({row.get("club_id", "") for row in active_staff if row.get("club_id")})

    for role in REQUIRED_STAFF_ROLES:
        if role not in active_roles:
            _add(results, "BLOCKER", f"staff:{role}", f"active staff role '{role}' not found")
        else:
            _add(results, "PASS", f"staff:{role}", f"active staff role '{role}' found")

    if not active_club_ids:
        _add(results, "BLOCKER", "club_id", "no active club_id found in staff_users")
    elif len(active_club_ids) > 1:
        _add(results, "WARN", "club_id", f"multiple active club_ids found: {', '.join(active_club_ids)}")
    else:
        _add(results, "PASS", "club_id", f"active club_id = {active_club_ids[0]}")

    club_id = active_club_ids[0] if active_club_ids else ""

    boats = [row for row in sheet.read_tab("boats") if row.get("club_id") == club_id and _is_active(row.get("is_active"))]
    if not boats:
        _add(results, "BLOCKER", "boats", f"no active boats found for club {club_id}")
    else:
        _add(results, "PASS", "boats", f"active boats = {len(boats)}")

    pricing_rows = [row for row in sheet.read_tab("pricing") if row.get("club_id") == club_id and row.get("valid_from", "") <= target_date]
    if not pricing_rows:
        _add(results, "BLOCKER", "pricing", f"no pricing row valid for {target_date} and club {club_id}")
    else:
        _add(results, "PASS", "pricing", f"pricing rows valid for {target_date} = {len(pricing_rows)}")

    target_weekday = weekday_iso0(target_date)
    schedule_rows = [
        row
        for row in sheet.read_tab("schedule")
        if row.get("club_id") == club_id and _is_active(row.get("is_active")) and str(row.get("weekday", "")) == str(target_weekday)
    ]
    if not schedule_rows:
        _add(results, "BLOCKER", "schedule", f"no active schedule rows found for weekday {target_weekday} and club {club_id}")
    else:
        _add(results, "PASS", "schedule", f"active schedule rows for weekday {target_weekday} = {len(schedule_rows)}")

    try:
        availability = get_availability_for_date(sheet, target_date, club_id)
        active_slots = [slot for slot in availability if slot.get("status") == "active"]
        if not active_slots:
            _add(results, "BLOCKER", "availability", f"no active slots available for {target_date}")
        else:
            _add(results, "PASS", "availability", f"active slots for {target_date} = {len(active_slots)}")
    except Exception as exc:
        _add(results, "BLOCKER", "availability", str(exc))

    booking_rows = sheet.read_tab("bookings")
    duplicate_booking_ids = _detect_duplicates(booking_rows, "booking_id")
    if duplicate_booking_ids:
        _add(results, "BLOCKER", "booking_id", f"duplicate booking_id values: {', '.join(duplicate_booking_ids)}")
    else:
        _add(results, "PASS", "booking_id", "no duplicate booking_id values")

    duplicate_client_ids = _detect_duplicates(sheet.read_tab("clients"), "client_id")
    if duplicate_client_ids:
        _add(results, "WARN", "client_id", f"duplicate client_id values: {', '.join(duplicate_client_ids)}")
    else:
        _add(results, "PASS", "client_id", "no duplicate client_id values")

    booking_rows_for_date = [row for row in booking_rows if row.get("club_id") == club_id and row.get("date") == target_date]
    missing_ride_type = [row.get("booking_id", "") for row in booking_rows_for_date if not row.get("ride_type")]
    if missing_ride_type:
        _add(results, "WARN", "ride_type", f"bookings missing ride_type on {target_date}: {', '.join(missing_ride_type)}")
    else:
        _add(results, "PASS", "ride_type", f"all bookings on {target_date} have ride_type")

    blockers = [item for item in results if item.level == "BLOCKER"]
    warnings = [item for item in results if item.level == "WARN"]

    return {
        "target_date": target_date,
        "blockers": len(blockers),
        "warnings": len(warnings),
        "checks": [item.__dict__ for item in results],
    }
