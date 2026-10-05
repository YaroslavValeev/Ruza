from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from ..models import BookingCreateRequest, BookingStatus
from .availability import get_availability_for_date
from .common import parse_bool
from .gender import infer_gender_from_full_name
from .payments import payment_summaries_by_booking
from .ride_runtime import (
    compute_elapsed_seconds,
    compute_remaining_seconds,
    iter_booking_slots,
    offset_time_text,
    parse_actual_duration_seconds,
    parse_sets_count,
    planned_duration_minutes,
    timer_state,
)

FINAL_BOOKING_STATUSES = {"done", "cancelled", "no_show"}
RIDE_TIMER_ONLY_STATUSES = {"in_progress", "done"}
ACTIVE_BOOKING_STATUSES = {"confirmed", "arrived", "ready", "in_progress", "late"}
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"arrived", "late", "cancelled", "no_show"},
    "arrived": {"ready", "late", "cancelled"},
    "ready": {"in_progress", "late", "cancelled"},
    "in_progress": {"done"},
    "late": {"arrived", "no_show", "cancelled"},
    "done": set(),
    "cancelled": set(),
    "no_show": set(),
}

RIDE_TYPE_NOTE_PREFIX = "[ride_type:"
WETSUIT_SIZE_NOTE_PREFIX = "[wetsuit_size:"
WETSUIT_GENDER_NOTE_PREFIX = "[wetsuit_gender:"
RIDE_RUNTIME_DEFAULTS = {
    "warmup_state": "pending",
    "timer_state": "idle",
    "timer_started_at": "",
    "timer_anchor_at": "",
    "elapsed_seconds": "0",
    "actual_duration_seconds": "0",
    "admin_notice_15_sent_at": "",
    "admin_notice_5_sent_at": "",
    "client_notice_15_sent_at": "",
    "client_notice_5_sent_at": "",
    "next_client_notified_at": "",
}


def _required_slot_times(time_text: str, sets_count: int) -> list[str]:
    return [offset_time_text(time_text, index) for index in range(sets_count)]


def _get_pricing(sheet: SheetWrapper, booking_date: str, club_id: str) -> dict[str, str | int]:
    candidates = [
        row
        for row in sheet.read_tab("pricing")
        if row.get("club_id") == club_id and row.get("valid_from", "") <= booking_date
    ]
    candidates.sort(key=lambda row: row.get("valid_from", ""), reverse=True)
    if not candidates:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pricing configured for selected date")

    row = candidates[0]
    return {
        "pricing_id": row.get("price_id", ""),
        "base_price": int(row.get("base_price") or 0),
        "coach_price": int(row.get("coach_price") or 0),
        "currency": row.get("currency") or "RUB",
    }


def _calculate_total_price(base_price: int, coach_price: int, discount: int, coach_required: bool) -> int:
    total = base_price + (coach_price if coach_required else 0) - discount
    return max(total, 0)


def _build_notes(
    notes: str,
    *,
    ride_type: str | None,
    wetsuit_required: bool,
    wetsuit_size: str | None,
    wetsuit_gender: str | None,
) -> str:
    chunks: list[str] = []
    clean_notes = notes.strip()
    if clean_notes:
        chunks.append(clean_notes)
    if ride_type:
        chunks.append(f"{RIDE_TYPE_NOTE_PREFIX}{ride_type}]")
    if wetsuit_required and wetsuit_size:
        chunks.append(f"{WETSUIT_SIZE_NOTE_PREFIX}{wetsuit_size}]")
    if wetsuit_required and wetsuit_gender:
        chunks.append(f"{WETSUIT_GENDER_NOTE_PREFIX}{wetsuit_gender}]")
    return "\n".join(chunks)


def _extract_booking_meta(raw_notes: str) -> tuple[str, str | None, bool, str | None, str | None]:
    clean_lines: list[str] = []
    ride_type: str | None = None
    wetsuit_required = False
    wetsuit_size: str | None = None
    wetsuit_gender: str | None = None

    for line in raw_notes.splitlines():
        normalized = line.strip()
        if normalized.startswith(RIDE_TYPE_NOTE_PREFIX) and normalized.endswith("]"):
            ride_type = normalized[len(RIDE_TYPE_NOTE_PREFIX) : -1] or None
            continue
        if normalized.startswith(WETSUIT_SIZE_NOTE_PREFIX) and normalized.endswith("]"):
            wetsuit_required = True
            wetsuit_size = normalized[len(WETSUIT_SIZE_NOTE_PREFIX) : -1] or None
            continue
        if normalized.startswith(WETSUIT_GENDER_NOTE_PREFIX) and normalized.endswith("]"):
            wetsuit_required = True
            wetsuit_gender = normalized[len(WETSUIT_GENDER_NOTE_PREFIX) : -1] or None
            continue
        clean_lines.append(line)

    return "\n".join(line for line in clean_lines if line.strip()), ride_type, wetsuit_required, wetsuit_size, wetsuit_gender


def _booking_to_item(
    row: dict[str, str],
    clients: dict[str, dict[str, str]],
    payment_summary: dict[str, str | int] | None = None,
) -> dict[str, str | int | bool]:
    client = clients.get(row.get("client_id", ""), {})
    notes, ride_type, wetsuit_required, wetsuit_size, wetsuit_gender = _extract_booking_meta(row.get("notes", ""))
    elapsed_seconds = compute_elapsed_seconds(row)
    actual_duration_seconds = parse_actual_duration_seconds(row)
    item: dict[str, str | int | bool] = {
        "booking_id": row.get("booking_id", ""),
        "client_id": row.get("client_id", ""),
        "client_name": client.get("full_name", ""),
        "client_phone": client.get("phone", ""),
        "date": row.get("date", ""),
        "time": row.get("time", ""),
        "boat_id": row.get("boat_id", ""),
        "status": row.get("status", "confirmed"),
        "coach_required": parse_bool(row.get("coach_required")),
        "coach_user_id": row.get("coach_user_id") or None,
        "ride_type": row.get("ride_type") or ride_type or "wakeboard",
        "sets_count": parse_sets_count(row),
        "planned_duration_minutes": planned_duration_minutes(row),
        "wetsuit_required": parse_bool(row.get("wetsuit_required")) or wetsuit_required,
        "wetsuit_size": row.get("wetsuit_size") or wetsuit_size,
        "wetsuit_gender": row.get("wetsuit_gender") or wetsuit_gender or infer_gender_from_full_name(client.get("full_name", "")),
        "warmup_state": row.get("warmup_state", "pending") or "pending",
        "timer_state": timer_state(row),
        "timer_started_at": row.get("timer_started_at", ""),
        "timer_anchor_at": row.get("timer_anchor_at", ""),
        "elapsed_seconds": elapsed_seconds,
        "remaining_seconds": compute_remaining_seconds(row),
        "actual_duration_seconds": actual_duration_seconds,
        "total_price": int(row.get("total_price") or 0),
        "notes": notes,
    }
    if payment_summary:
        item.update(
            {
                "payment_status": str(payment_summary["payment_status"]),
                "paid_amount_minor": int(payment_summary["paid_amount_minor"]),
                "refunded_amount_minor": int(payment_summary["refunded_amount_minor"]),
                "net_paid_minor": int(payment_summary["net_paid_minor"]),
                "balance_due_minor": int(payment_summary["balance_due_minor"]),
            }
        )
    return item


def create_booking(
    sheet: SheetWrapper,
    payload: BookingCreateRequest,
    *,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, str | int]:
    booking_id = payload.booking_id or f"bkg-{uuid4()}"
    booking_date = payload.date.isoformat()

    existing = sheet.find("bookings", {"booking_id": booking_id})
    if existing:
        return {
            "booking_id": booking_id,
            "status": existing[0].get("status", "confirmed"),
            "total_price": int(existing[0].get("total_price") or 0),
        }

    availability = get_availability_for_date(sheet, booking_date, club_id)
    required_slot_times = _required_slot_times(payload.time, payload.sets_count)
    matching_slots = {
        slot["time"]: slot
        for slot in availability
        if slot["boat_id"] == payload.boat_id and slot["time"] in required_slot_times and slot["status"] == "active"
    }
    if len(matching_slots) != len(required_slot_times):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No capacity for selected slot duration")
    if any(matching_slots[time_text]["available"] <= 0 for time_text in required_slot_times):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No capacity for selected slot duration")

    pricing = _get_pricing(sheet, booking_date, club_id)
    base_price = int(pricing["base_price"])
    coach_price = int(pricing["coach_price"])
    total_price = _calculate_total_price(base_price, coach_price, payload.discount, payload.coach_required)
    now_iso = datetime.now(timezone.utc).isoformat()
    booking_row = {
        "booking_id": booking_id,
        "club_id": club_id,
        "client_id": payload.client_id,
        "date": booking_date,
        "time": payload.time,
        "boat_id": payload.boat_id,
        "coach_required": payload.coach_required,
        "coach_user_id": payload.coach_user_id or "",
        "status": "confirmed",
        "pricing_id": pricing["pricing_id"],
        "price_base": base_price,
        "price_coach": coach_price if payload.coach_required else 0,
        "discount": payload.discount,
        "currency": pricing["currency"],
        "total_price": total_price,
        "created_by": actor_staff_user_id,
        "created_at": now_iso,
        "updated_at": now_iso,
        "notes": _build_notes(
            payload.notes,
            ride_type=payload.ride_type,
            wetsuit_required=payload.wetsuit_required,
            wetsuit_size=payload.wetsuit_size,
            wetsuit_gender=payload.wetsuit_gender,
        ),
        "ride_type": payload.ride_type,
        "sets_count": payload.sets_count,
        "wetsuit_required": payload.wetsuit_required,
        "wetsuit_size": payload.wetsuit_size or "",
        "wetsuit_gender": payload.wetsuit_gender or "",
        **RIDE_RUNTIME_DEFAULTS,
    }
    sheet.append_row("bookings", booking_row, unique_key="booking_id")

    booking_rows = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and row.get("date") == booking_date
        and row.get("boat_id") == payload.boat_id
        and row.get("status") not in {"cancelled", "no_show"}
    ]
    for slot_time in required_slot_times:
        occupied = sum(1 for row in booking_rows if slot_time in iter_booking_slots(row))
        if occupied > int(matching_slots[slot_time]["capacity"]):
            sheet.update_by_id(
                "bookings",
                "booking_id",
                booking_id,
                {"status": "cancelled", "updated_at": now_iso, "notes": "Auto-cancelled after duration overbook protection"},
                actor=actor_staff_user_id,
                audit_entity="booking",
            )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No capacity for selected slot duration")

    sheet.write_audit(
        action="create",
        entity="booking",
        entity_id=booking_id,
        diff_json=booking_row,
        actor=actor_staff_user_id,
    )
    return {"booking_id": booking_id, "status": "confirmed", "total_price": total_price}


def list_bookings(
    sheet: SheetWrapper,
    *,
    club_id: str,
    target_date: str,
    coach_user_id: str | None = None,
    boat_id: str | None = None,
) -> list[dict[str, str | int | bool]]:
    clients = {row.get("client_id", ""): row for row in sheet.read_tab("clients") if row.get("club_id") == club_id}
    rows = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id and row.get("date") == target_date
    ]
    if coach_user_id:
        rows = [
            row
            for row in rows
            if parse_bool(row.get("coach_required")) and row.get("coach_user_id") == coach_user_id
        ]
    if boat_id is not None:
        rows = [row for row in rows if row.get("boat_id") == boat_id]
    rows.sort(key=lambda row: (row.get("time", ""), row.get("boat_id", ""), row.get("booking_id", "")))
    payments = [row for row in sheet.read_tab("payments") if row.get("club_id") == club_id]
    summaries = payment_summaries_by_booking(rows, payments)
    return [_booking_to_item(row, clients, summaries.get(row.get("booking_id", ""))) for row in rows]


def get_booking_row(sheet: SheetWrapper, *, booking_id: str, club_id: str) -> dict[str, str]:
    rows = sheet.find("bookings", {"booking_id": booking_id})
    row = next((item for item in rows if item.get("club_id") == club_id), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return row


def update_booking_status(
    sheet: SheetWrapper,
    *,
    booking_id: str,
    status_value: BookingStatus,
    actor_staff_user_id: str,
    club_id: str,
    allow_ride_runtime: bool = False,
) -> dict[str, str | int | bool]:
    row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)

    current_status = row.get("status", "confirmed")
    if status_value in RIDE_TIMER_ONLY_STATUSES and not allow_ride_runtime and current_status != status_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ride start and finish are only available through the timer",
        )
    if current_status == status_value:
        clients = {client.get("client_id", ""): client for client in sheet.read_tab("clients") if client.get("club_id") == club_id}
        payments = [
            payment
            for payment in sheet.read_tab("payments")
            if payment.get("club_id") == club_id and payment.get("booking_id") == booking_id
        ]
        summary = payment_summaries_by_booking([row], payments).get(booking_id)
        return _booking_to_item(row, clients, summary)

    allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if status_value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition: {current_status} -> {status_value}",
        )

    patched = sheet.update_by_id(
        "bookings",
        "booking_id",
        booking_id,
        {"status": status_value, "updated_at": datetime.now(timezone.utc).isoformat()},
        actor=actor_staff_user_id,
        audit_entity="booking",
    )
    clients = {client.get("client_id", ""): client for client in sheet.read_tab("clients") if client.get("club_id") == club_id}
    payments = [
        payment
        for payment in sheet.read_tab("payments")
        if payment.get("club_id") == club_id and payment.get("booking_id") == booking_id
    ]
    summary = payment_summaries_by_booking([patched], payments).get(booking_id)
    return _booking_to_item(patched, clients, summary)

