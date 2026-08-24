from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from ..models import CheckinCreateRequest, CheckinStatus
from .bookings import update_booking_status
from .common import parse_bool, phones_match


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_client_by_phone(sheet: SheetWrapper, club_id: str, phone: str) -> dict[str, str] | None:
    for row in sheet.read_tab("clients"):
        if row.get("club_id") != club_id:
            continue
        if phones_match(str(row.get("phone", "")), phone):
            return row
    return None


def _find_booking_for_checkin(
    sheet: SheetWrapper,
    *,
    club_id: str,
    target_date: str,
    client_id: str | None = None,
    booking_id: str | None = None,
) -> dict[str, str]:
    rows = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and row.get("date") == target_date
        and row.get("status") not in {"cancelled", "done", "no_show"}
    ]
    if booking_id:
        match = next((row for row in rows if row.get("booking_id") == booking_id), None)
        if match is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found for check-in")
        return match

    if not client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_id or booking_id required")

    client_bookings = [row for row in rows if row.get("client_id") == client_id]
    if not client_bookings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active booking found for client")
    client_bookings.sort(key=lambda row: row.get("time", ""))
    return client_bookings[0]


def _client_consent_flags(sheet: SheetWrapper, club_id: str, client_id: str) -> tuple[bool, bool]:
    for row in sheet.read_tab("clients"):
        if row.get("club_id") == club_id and row.get("client_id") == client_id:
            return (
                parse_bool(row.get("consent_face")),
                parse_bool(row.get("consent_voice")),
            )
    return False, False


def _checkin_to_item(sheet: SheetWrapper, club_id: str, row: dict[str, str]) -> dict[str, str | bool | None]:
    client_id = row.get("client_id", "")
    consent_face, consent_voice = _client_consent_flags(sheet, club_id, client_id)
    return {
        "checkin_id": row.get("checkin_id", ""),
        "club_id": row.get("club_id", ""),
        "booking_id": row.get("booking_id", ""),
        "client_id": client_id,
        "method": row.get("method", "manual"),
        "status": row.get("status", "arrived"),
        "ts": row.get("ts", ""),
        "operator_user_id": row.get("operator_user_id") or None,
        "consent_face": consent_face,
        "consent_voice": consent_voice,
    }


def list_checkins(sheet: SheetWrapper, *, club_id: str, target_date: str) -> list[dict[str, str | None]]:
    bookings = {
        row.get("booking_id", ""): row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id and row.get("date") == target_date
    }
    rows = [
        row
        for row in sheet.read_tab("checkins")
        if row.get("club_id") == club_id and bookings.get(row.get("booking_id", ""), {}).get("date") == target_date
    ]
    rows.sort(key=lambda row: row.get("ts", ""), reverse=True)
    return [_checkin_to_item(sheet, club_id, row) for row in rows]


def create_checkin(
    sheet: SheetWrapper,
    payload: CheckinCreateRequest,
    *,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, str | None]:
    target_date = payload.date.isoformat()
    client_id = payload.client_id
    booking_id = payload.booking_id

    if payload.method == "phone":
        if not payload.phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phone is required for phone check-in")
        client = _find_client_by_phone(sheet, club_id, payload.phone)
        if client is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found by phone")
        client_id = client.get("client_id", "")

    booking = _find_booking_for_checkin(
        sheet,
        club_id=club_id,
        target_date=target_date,
        client_id=client_id,
        booking_id=booking_id,
    )
    booking_id = booking.get("booking_id", "")
    client_id = booking.get("client_id", "")

    checkin_status: CheckinStatus = payload.status
    booking_status = "arrived" if checkin_status == "arrived" else "ready" if checkin_status == "ready" else "late"

    checkin_id = f"chk-{uuid4()}"
    row = {
        "checkin_id": checkin_id,
        "club_id": club_id,
        "booking_id": booking_id,
        "client_id": client_id,
        "method": payload.method,
        "status": checkin_status,
        "ts": _utc_now_iso(),
        "operator_user_id": actor_staff_user_id,
    }
    sheet.append_row("checkins", row, unique_key="checkin_id")
    sheet.write_audit(
        action="create",
        entity="checkin",
        entity_id=checkin_id,
        diff_json=row,
        actor=actor_staff_user_id,
    )

    update_booking_status(
        sheet,
        booking_id=booking_id,
        status_value=booking_status,  # type: ignore[arg-type]
        actor_staff_user_id=actor_staff_user_id,
        club_id=club_id,
    )

    return _checkin_to_item(sheet, club_id, row)


def mark_late_checkins(
    sheet: SheetWrapper,
    *,
    club_id: str,
    target_date: str,
    actor_staff_user_id: str,
    minutes_before: int = 10,
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    target = date.fromisoformat(target_date)
    marked = 0

    bookings = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id
        and row.get("date") == target_date
        and row.get("status") == "confirmed"
    ]
    existing_checkins = {
        row.get("booking_id", "")
        for row in sheet.read_tab("checkins")
        if row.get("club_id") == club_id
    }

    for booking in bookings:
        booking_id = booking.get("booking_id", "")
        if booking_id in existing_checkins:
            continue

        time_text = booking.get("time", "00:00")
        hour, minute = (int(part) for part in time_text.split(":"))
        slot_start = datetime(target.year, target.month, target.day, hour, minute, tzinfo=timezone.utc)
        if now >= slot_start - timedelta(minutes=minutes_before):
            update_booking_status(
                sheet,
                booking_id=booking_id,
                status_value="late",
                actor_staff_user_id=actor_staff_user_id,
                club_id=club_id,
            )
            checkin_id = f"chk-{uuid4()}"
            row = {
                "checkin_id": checkin_id,
                "club_id": club_id,
                "booking_id": booking_id,
                "client_id": booking.get("client_id", ""),
                "method": "system",
                "status": "late",
                "ts": _utc_now_iso(),
                "operator_user_id": actor_staff_user_id,
            }
            sheet.append_row("checkins", row, unique_key="checkin_id")
            marked += 1

    return {"marked_late": marked}
