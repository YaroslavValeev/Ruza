from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import BookingCreateRequest, BookingCreateResponse, BookingItem, BookingStatusUpdateRequest
from ..services.bookings import create_booking, list_bookings, update_booking_status
from ..services.pilot import get_pilot_boat_id


PILOT_ALLOWED_STATUSES = {"in_progress", "done"}


router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("", response_model=list[BookingItem])
def get_bookings(
    date_value: date = Query(..., alias="date"),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot", "coach")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[BookingItem]:
    coach_filter = user.staff_user_id if user.role == "coach" else None
    return [
        BookingItem(**item)
        for item in list_bookings(
            sheet,
            club_id=user.club_id,
            target_date=date_value.isoformat(),
            coach_user_id=coach_filter,
        )
    ]


@router.post("", response_model=BookingCreateResponse)
def post_booking(
    payload: BookingCreateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> BookingCreateResponse:
    booking = create_booking(
        sheet,
        payload,
        actor_staff_user_id=user.staff_user_id,
        club_id=user.club_id,
    )
    return BookingCreateResponse(**booking)


@router.patch("/{booking_id}/status", response_model=BookingItem)
def patch_booking_status(
    booking_id: str,
    payload: BookingStatusUpdateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> BookingItem:
    if user.role == "pilot":
        if payload.status not in PILOT_ALLOWED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pilot can only start and finish rides",
            )
        assigned_boat = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id)
        booking_rows = sheet.find("bookings", {"booking_id": booking_id})
        booking_row = next((item for item in booking_rows if item.get("club_id") == user.club_id), None)
        if not assigned_boat or not booking_row or booking_row.get("boat_id") != assigned_boat:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pilot can only update assigned boat")
    return BookingItem(
        **update_booking_status(
            sheet,
            booking_id=booking_id,
            status_value=payload.status,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )
