from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..config import Settings, get_settings
from ..dependencies import get_sheet_wrapper
from ..models import (
    BookingCreateRequest,
    BookingCreateResponse,
    BookingItem,
    BookingPrepUpdateRequest,
    BookingStatusUpdateRequest,
    RideTimerActionRequest,
)
from ..services.bookings import create_booking, get_booking_row, list_bookings, update_booking_status
from ..services.pilot import get_pilot_boat_id
from ..services.shift_timer import run_timer_action, update_booking_prep


PILOT_ALLOWED_STATUSES = {"in_progress", "done"}


router = APIRouter(prefix="/bookings", tags=["bookings"])


def _assert_pilot_booking_access(sheet: SheetWrapper, *, booking_id: str, user: AuthUser) -> None:
    assigned_boat = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id)
    booking_row = get_booking_row(sheet, booking_id=booking_id, club_id=user.club_id)
    if not assigned_boat or booking_row.get("boat_id") != assigned_boat:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pilot can only update assigned boat")


@router.get("", response_model=list[BookingItem])
def get_bookings(
    date_value: date = Query(..., alias="date"),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot", "coach")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[BookingItem]:
    coach_filter = user.staff_user_id if user.role == "coach" else None
    boat_filter = None
    if user.role == "pilot":
        boat_filter = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id) or ""
    return [
        BookingItem(**item)
        for item in list_bookings(
            sheet,
            club_id=user.club_id,
            target_date=date_value.isoformat(),
            coach_user_id=coach_filter,
            boat_id=boat_filter,
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
    if user.role == "operator" and payload.status in PILOT_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator can only hand off bookings to pilot",
        )
    if user.role == "pilot":
        if payload.status not in PILOT_ALLOWED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pilot can only start and finish rides",
            )
        _assert_pilot_booking_access(sheet, booking_id=booking_id, user=user)
    if payload.status in PILOT_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ride start and finish are only available through the timer",
        )
    return BookingItem(
        **update_booking_status(
            sheet,
            booking_id=booking_id,
            status_value=payload.status,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )


@router.patch("/{booking_id}/prep", response_model=BookingItem)
def patch_booking_prep(
    booking_id: str,
    payload: BookingPrepUpdateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> BookingItem:
    if user.role == "pilot":
        _assert_pilot_booking_access(sheet, booking_id=booking_id, user=user)
    return BookingItem(
        **update_booking_prep(
            sheet,
            settings,
            booking_id=booking_id,
            arrival_action=payload.arrival_action,
            warmup_state=payload.warmup_state,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )


@router.post("/{booking_id}/timer-action", response_model=BookingItem)
def post_timer_action(
    booking_id: str,
    payload: RideTimerActionRequest,
    user: AuthUser = Depends(require_roles("admin", "pilot")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> BookingItem:
    if user.role == "pilot":
        _assert_pilot_booking_access(sheet, booking_id=booking_id, user=user)
    return BookingItem(
        **run_timer_action(
            sheet,
            settings,
            booking_id=booking_id,
            action=payload.action,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )
