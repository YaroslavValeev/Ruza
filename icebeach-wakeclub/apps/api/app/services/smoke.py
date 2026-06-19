from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from ..models import BookingCreateRequest, RideType
from .availability import get_availability_for_date
from .bookings import create_booking, list_bookings, update_booking_status
from .clients import list_clients
from .kpi import get_kpi_summary
from .pilot import get_pilot_queue

SMOKE_RIDE_TYPE: RideType = "skim"
SMOKE_WETSUIT_SIZE = "XL"
SMOKE_WETSUIT_GENDER = "male"
SMOKE_NOTES = "smoke-test-dashboard"


def _add(checks: list[dict[str, str]], level: str, code: str, message: str) -> None:
    checks.append({"level": level, "code": code, "message": message})


def run_smoke_check(
    sheet: SheetWrapper,
    *,
    target_date: str,
    club_id: str,
    actor_staff_user_id: str,
) -> dict[str, object]:
    checks: list[dict[str, str]] = []
    created_booking_id: str | None = None
    selected_client_id: str | None = None
    selected_slot: str | None = None

    clients = list_clients(sheet, club_id, query="")
    if not clients:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Smoke check requires at least one client")
    client = clients[0]
    selected_client_id = str(client.get("client_id") or "")
    _add(checks, "PASS", "clients.query", f"client={selected_client_id}")

    availability = get_availability_for_date(sheet, target_date, club_id)
    slot = next(
        (item for item in reversed(availability) if int(item.get("available") or 0) > 0 and item.get("status") == "active"),
        None,
    )
    if not slot:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Smoke check requires one free slot")
    selected_slot = f"{slot['date']} {slot['time']} {slot['boat_id']}"
    _add(checks, "PASS", "availability.slot", selected_slot)

    payload = BookingCreateRequest(
        client_id=selected_client_id,
        date=date.fromisoformat(target_date),
        time=str(slot["time"]),
        boat_id=str(slot["boat_id"]),
        coach_required=False,
        ride_type=SMOKE_RIDE_TYPE,
        wetsuit_required=True,
        wetsuit_size=SMOKE_WETSUIT_SIZE,
        wetsuit_gender=SMOKE_WETSUIT_GENDER,
        discount=0,
        notes=SMOKE_NOTES,
    )

    try:
        created = create_booking(sheet, payload, actor_staff_user_id=actor_staff_user_id, club_id=club_id)
        created_booking_id = str(created["booking_id"])
        _add(checks, "PASS", "bookings.create", f"created={created_booking_id}")

        bookings = list_bookings(sheet, club_id=club_id, target_date=target_date)
        created_item = next((item for item in bookings if item.get("booking_id") == created_booking_id), None)
        if created_item is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Created booking missing from list")
        _add(checks, "PASS", "bookings.persisted", f"status={created_item.get('status')}")

        if created_item.get("ride_type") != SMOKE_RIDE_TYPE:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Persisted ride_type={created_item.get('ride_type')}")
        _add(checks, "PASS", "bookings.ride_type", f"ride_type={created_item.get('ride_type')}")

        if created_item.get("wetsuit_gender") != SMOKE_WETSUIT_GENDER:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Persisted wetsuit_gender={created_item.get('wetsuit_gender')}")
        _add(checks, "PASS", "bookings.wetsuit_gender", f"gender={created_item.get('wetsuit_gender')}")

        if created_item.get("wetsuit_size") != SMOKE_WETSUIT_SIZE:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Persisted wetsuit_size={created_item.get('wetsuit_size')}")
        _add(checks, "PASS", "bookings.wetsuit_size", f"size={created_item.get('wetsuit_size')}")

        pilot_queue = get_pilot_queue(
            sheet,
            boat_id=str(slot["boat_id"]),
            club_id=club_id,
            date_from=target_date,
            date_to=target_date,
        )
        pilot_item = next((item for item in pilot_queue if item.get("booking_id") == created_booking_id), None)
        if pilot_item is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Booking missing in pilot queue")
        _add(checks, "PASS", "pilot.queue", f"booking visible for boat={slot['boat_id']}")

        kpi = get_kpi_summary(sheet, club_id, period="season", date_from=target_date)
        ride_breakdown = list(kpi.get("ride_breakdown") or [])
        if len(ride_breakdown) < 3:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="KPI ride breakdown incomplete")
        _add(checks, "PASS", "kpi.breakdown", "ride breakdown present")
    except HTTPException as exc:
        _add(checks, "FAIL", "smoke", str(exc.detail))
    except Exception as exc:  # pragma: no cover - defensive operational path
        _add(checks, "FAIL", "smoke", str(exc))
    finally:
        if created_booking_id:
            try:
                cancelled = update_booking_status(
                    sheet,
                    booking_id=created_booking_id,
                    status_value="cancelled",
                    actor_staff_user_id=actor_staff_user_id,
                    club_id=club_id,
                )
                _add(checks, "PASS", "bookings.cancel", f"status={cancelled.get('status')}")
            except Exception as exc:  # pragma: no cover - operational visibility matters more than strict coverage here
                _add(checks, "FAIL", "bookings.cancel", str(exc))

    failures = [item for item in checks if item["level"] == "FAIL"]
    return {
        "target_date": target_date,
        "ok": not failures,
        "created_booking_id": created_booking_id,
        "selected_client_id": selected_client_id,
        "selected_slot": selected_slot,
        "checks": checks,
    }
