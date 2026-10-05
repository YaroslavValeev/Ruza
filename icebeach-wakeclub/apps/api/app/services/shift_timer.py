from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from ..config import Settings
from .availability import get_availability_for_date
from .bookings import get_booking_row, list_bookings, update_booking_status
from .notifications import send_admin_notice, send_client_notice
from .ride_runtime import compute_elapsed_seconds, iter_booking_slots, offset_time_text, parse_sets_count, resolve_club_timezone, slot_start_local


def _now(now: datetime | None = None) -> datetime:
    if now is not None:
        return now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _booking_item(sheet: SheetWrapper, *, booking_id: str, club_id: str, target_date: str) -> dict[str, object]:
    bookings = list_bookings(sheet, club_id=club_id, target_date=target_date)
    item = next((booking for booking in bookings if booking.get("booking_id") == booking_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return item


def _patch_booking_runtime(
    sheet: SheetWrapper,
    *,
    booking_id: str,
    patch: dict[str, str | int],
    actor_staff_user_id: str,
) -> None:
    if not patch:
        return
    sheet.update_by_id(
        "bookings",
        "booking_id",
        booking_id,
        patch,
        actor=actor_staff_user_id,
        audit_entity="booking",
    )


def _client_row(sheet: SheetWrapper, *, club_id: str, client_id: str) -> dict[str, str]:
    client = next(
        (row for row in sheet.find("clients", {"client_id": client_id}) if row.get("club_id") == club_id),
        None,
    )
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def _club_zone(sheet: SheetWrapper, club_id: str):
    row = next((item for item in sheet.read_tab("clubs") if item.get("club_id") == club_id), None)
    return resolve_club_timezone((row or {}).get("timezone"))


def _slot_start(row: dict[str, str], zone) -> datetime:
    return slot_start_local(row.get("date", ""), row.get("time", "00:00"), zone)


def _next_slot_available(sheet: SheetWrapper, *, row: dict[str, str], club_id: str) -> bool:
    next_slot_time = offset_time_text(row.get("time", "00:00"), parse_sets_count(row))
    availability = get_availability_for_date(sheet, row.get("date", ""), club_id)
    slot = next(
        (
            item
            for item in availability
            if item["boat_id"] == row.get("boat_id", "")
            and item["time"] == next_slot_time
            and item["status"] == "active"
        ),
        None,
    )
    return bool(slot and int(slot["available"]) > 0)


def _next_client_candidate(sheet: SheetWrapper, *, row: dict[str, str], club_id: str) -> dict[str, str] | None:
    next_slot_time = offset_time_text(row.get("time", "00:00"), parse_sets_count(row))
    boat_id = row.get("boat_id", "")
    bookings = [
        booking
        for booking in sheet.read_tab("bookings")
        if booking.get("club_id") == club_id
        and booking.get("date") == row.get("date", "")
        and booking.get("boat_id") == boat_id
        and booking.get("booking_id") != row.get("booking_id")
        and booking.get("status") not in {"cancelled", "done", "no_show"}
        and booking.get("time", "") > next_slot_time
    ]
    bookings.sort(key=lambda item: (item.get("time", ""), item.get("booking_id", "")))
    return bookings[0] if bookings else None


def update_booking_prep(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    booking_id: str,
    arrival_action: str | None,
    warmup_state: str | None,
    actor_staff_user_id: str,
    club_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
    current_status = row.get("status", "confirmed")
    current_now = _now(now)
    runtime_patch: dict[str, str | int] = {}

    if arrival_action:
        if arrival_action == "arrived":
            if current_status not in {"confirmed", "late", "arrived"}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Arrival can only be confirmed before the ride starts")
            if current_status != "arrived":
                update_booking_status(
                    sheet,
                    booking_id=booking_id,
                    status_value="arrived",
                    actor_staff_user_id=actor_staff_user_id,
                    club_id=club_id,
                )
                row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
                current_status = row.get("status", "confirmed")
        elif arrival_action == "late":
            if current_status not in {"confirmed", "late"}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Late can only be marked before arrival")
            if current_status != "late":
                update_booking_status(
                    sheet,
                    booking_id=booking_id,
                    status_value="late",
                    actor_staff_user_id=actor_staff_user_id,
                    club_id=club_id,
                )
                row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
                current_status = row.get("status", "confirmed")
            minutes_to_start = int((_slot_start(row, _club_zone(sheet, club_id)) - current_now).total_seconds() // 60)
            if minutes_to_start <= 15 and not row.get("client_notice_15_sent_at"):
                client = _client_row(sheet, club_id=club_id, client_id=row.get("client_id", ""))
                send_client_notice(
                    sheet,
                    settings,
                    booking_id=booking_id,
                    client_row=client,
                    actor=actor_staff_user_id,
                    title="Сессия ещё в силе?",
                    message="До старта осталось 15 минут. Если заезд в силе, пожалуйста, подойдите к старту и дайте знать оператору.",
                )
                runtime_patch["client_notice_15_sent_at"] = current_now.isoformat()

    row_after_arrival = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
    if warmup_state is not None:
        if row_after_arrival.get("status", "confirmed") not in {"arrived", "ready"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Warmup can only be set after arrival")
        runtime_patch["warmup_state"] = warmup_state

    _patch_booking_runtime(
        sheet,
        booking_id=booking_id,
        patch=runtime_patch,
        actor_staff_user_id=actor_staff_user_id,
    )
    final_row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
    return _booking_item(sheet, booking_id=booking_id, club_id=club_id, target_date=final_row.get("date", ""))


def run_timer_action(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    booking_id: str,
    action: str,
    actor_staff_user_id: str,
    club_id: str,
    now: datetime | None = None,
) -> dict[str, object]:
    row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
    current_now = _now(now)
    booking_status = row.get("status", "confirmed")
    current_timer_state = row.get("timer_state", "idle") or "idle"
    runtime_patch: dict[str, str | int] = {}

    if action == "start":
        if booking_status != "ready":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride can only start from ready")
        update_booking_status(
            sheet,
            booking_id=booking_id,
            status_value="in_progress",
            actor_staff_user_id=actor_staff_user_id,
            club_id=club_id,
            allow_ride_runtime=True,
        )
        runtime_patch.update(
            {
                "timer_state": "running",
                "timer_started_at": row.get("timer_started_at") or current_now.isoformat(),
                "timer_anchor_at": current_now.isoformat(),
            }
        )
    elif action == "pause":
        if booking_status != "in_progress" or current_timer_state != "running":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride can only pause while running on water")
        runtime_patch.update(
            {
                "timer_state": "paused",
                "elapsed_seconds": compute_elapsed_seconds(row, now=current_now),
                "timer_anchor_at": "",
            }
        )
    elif action == "stop":
        if booking_status != "in_progress" or current_timer_state not in {"running", "paused"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride can only stop after it has started")
        elapsed_seconds = compute_elapsed_seconds(row, now=current_now)
        runtime_patch.update(
            {
                "timer_state": "completed",
                "elapsed_seconds": elapsed_seconds,
                "actual_duration_seconds": elapsed_seconds,
                "timer_anchor_at": "",
            }
        )
        _patch_booking_runtime(
            sheet,
            booking_id=booking_id,
            patch=runtime_patch,
            actor_staff_user_id=actor_staff_user_id,
        )
        runtime_patch = {}
        update_booking_status(
            sheet,
            booking_id=booking_id,
            status_value="done",
            actor_staff_user_id=actor_staff_user_id,
            club_id=club_id,
            allow_ride_runtime=True,
        )
    elif action == "add_set":
        if booking_status != "in_progress":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Extra set can only be added while on water")
        if not _next_slot_available(sheet, row=row, club_id=club_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Next slot is not free for an extra set")
        runtime_patch["sets_count"] = parse_sets_count(row) + 1
    elif action == "notify_next_client":
        # One successful notice per booking. A repeat click must not send Telegram again.
        if not str(row.get("next_client_notified_at") or "").strip():
            next_client_booking = _next_client_candidate(sheet, row=row, club_id=club_id)
            if next_client_booking is None or not _next_slot_available(sheet, row=row, club_id=club_id):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No earlier start notice can be sent for the next client")
            client = _client_row(sheet, club_id=club_id, client_id=next_client_booking.get("client_id", ""))
            send_client_notice(
                sheet,
                settings,
                booking_id=next_client_booking.get("booking_id", ""),
                client_row=client,
                actor=actor_staff_user_id,
                title="Можно подойти раньше",
                message=f"Следующий свободный старт освободился раньше. Если вам удобно, подойдите к старту к {offset_time_text(row.get('time', '00:00'), parse_sets_count(row))}.",
            )
            runtime_patch["next_client_notified_at"] = current_now.isoformat()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported timer action")

    _patch_booking_runtime(
        sheet,
        booking_id=booking_id,
        patch=runtime_patch,
        actor_staff_user_id=actor_staff_user_id,
    )
    final_row = get_booking_row(sheet, booking_id=booking_id, club_id=club_id)
    return _booking_item(sheet, booking_id=booking_id, club_id=club_id, target_date=final_row.get("date", ""))


def get_shift_live(
    sheet: SheetWrapper,
    *,
    club_id: str,
    target_date: str,
    role: str,
    boat_id: str | None = None,
) -> dict[str, object]:
    bookings = list_bookings(sheet, club_id=club_id, target_date=target_date)
    if boat_id:
        bookings = [booking for booking in bookings if booking.get("boat_id") == boat_id]
    focus = None
    if bookings:
        def rank(booking: dict[str, object]) -> tuple[int, str]:
            status = str(booking.get("status", "confirmed"))
            warmup_state = str(booking.get("warmup_state", "pending"))
            if status == "in_progress":
                return (0, str(booking.get("time", "")))
            if role in {"admin", "operator"}:
                if status in {"confirmed", "late"}:
                    return (1, str(booking.get("time", "")))
                if status == "arrived" and warmup_state == "pending":
                    return (2, str(booking.get("time", "")))
                if status == "arrived":
                    return (3, str(booking.get("time", "")))
                if status == "ready":
                    return (4, str(booking.get("time", "")))
            elif role == "pilot":
                if status == "ready":
                    return (1, str(booking.get("time", "")))
                if status == "arrived":
                    return (2, str(booking.get("time", "")))
                if status in {"confirmed", "late"}:
                    return (3, str(booking.get("time", "")))
            else:
                if status == "ready":
                    return (1, str(booking.get("time", "")))
                if status == "arrived":
                    return (2, str(booking.get("time", "")))
                if status in {"confirmed", "late"}:
                    return (3, str(booking.get("time", "")))
            return (9, str(booking.get("time", "")))

        focus = sorted(bookings, key=rank)[0]
    if role == "marketing_read" and focus is not None:
        focus = dict(focus)
        focus["client_phone"] = ""
    return {"date": target_date, "focus_booking": focus}


def process_shift_reminders(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    club_id: str,
    actor_staff_user_id: str,
    now: datetime | None = None,
) -> dict[str, int]:
    current_now = _now(now)
    zone = _club_zone(sheet, club_id)
    target_date = current_now.astimezone(zone).date().isoformat()
    admin_notices = 0
    client_notices = 0

    rows = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and row.get("date") == target_date
        and row.get("status") in {"confirmed", "late"}
    ]

    for row in rows:
        booking_id = row.get("booking_id", "")
        minutes_to_start = int((_slot_start(row, zone) - current_now).total_seconds() // 60)
        runtime_patch: dict[str, str] = {}
        if 0 <= minutes_to_start <= 15 and row.get("status") == "confirmed" and not row.get("admin_notice_15_sent_at"):
            send_admin_notice(
                sheet,
                settings,
                booking_id=booking_id,
                actor=actor_staff_user_id,
                title="Скоро старт заезда",
                message=f"До старта клиента осталось 15 минут. Откройте смену и отметьте фактический статус по брони {booking_id}.",
            )
            runtime_patch["admin_notice_15_sent_at"] = current_now.isoformat()
            admin_notices += 1
        if 0 <= minutes_to_start <= 5 and row.get("status") in {"confirmed", "late"} and not row.get("admin_notice_5_sent_at"):
            send_admin_notice(
                sheet,
                settings,
                booking_id=booking_id,
                actor=actor_staff_user_id,
                title="Старт через 5 минут",
                message=f"До старта клиента осталось 5 минут. Проверьте бронирование {booking_id} и зафиксируйте фактический статус.",
            )
            runtime_patch["admin_notice_5_sent_at"] = current_now.isoformat()
            admin_notices += 1
        if (
            0 <= minutes_to_start <= 5
            and row.get("status") == "late"
            and row.get("client_notice_15_sent_at")
            and not row.get("client_notice_5_sent_at")
        ):
            client = _client_row(sheet, club_id=club_id, client_id=row.get("client_id", ""))
            send_client_notice(
                sheet,
                settings,
                booking_id=booking_id,
                client_row=client,
                actor=actor_staff_user_id,
                title="До старта 5 минут",
                message="Старт уже близко: до заезда осталось 5 минут. Пожалуйста, подойдите к старту и будьте готовы, включая короткую разминку.",
            )
            runtime_patch["client_notice_5_sent_at"] = current_now.isoformat()
            client_notices += 1
        _patch_booking_runtime(
            sheet,
            booking_id=booking_id,
            patch=runtime_patch,
            actor_staff_user_id=actor_staff_user_id,
        )

    return {"admin_notices_sent": admin_notices, "client_notices_sent": client_notices}
