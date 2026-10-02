from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import BookingItem, CheckinItem, ShiftLiveResponse, ShiftSummary, ShiftTodayResponse
from ..services.pilot import get_pilot_boat_id
from ..services.shift import get_shift_today
from ..services.shift_timer import get_shift_live


router = APIRouter(prefix="/shift", tags=["shift"])


@router.get("/today", response_model=ShiftTodayResponse)
def shift_today(
    date_value: date | None = Query(default=None, alias="date"),
    user: AuthUser = Depends(require_roles("admin", "operator", "coach")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> ShiftTodayResponse:
    target = date_value or date.today()
    target_text = target.isoformat()
    payload = get_shift_today(sheet, club_id=user.club_id, target_date=target_text)
    return ShiftTodayResponse(
        date=target,
        bookings=[BookingItem(**item) for item in payload["bookings"]],  # type: ignore[arg-type]
        checkins=[CheckinItem(**item) for item in payload["checkins"]],  # type: ignore[arg-type]
        summary=ShiftSummary(**payload["summary"]),  # type: ignore[arg-type]
    )


@router.get("/live", response_model=ShiftLiveResponse)
def shift_live(
    date_value: date | None = Query(default=None, alias="date"),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot", "coach", "marketing_read")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> ShiftLiveResponse:
    target = date_value or date.today()
    boat_id = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id) if user.role == "pilot" else None
    payload = get_shift_live(
        sheet,
        club_id=user.club_id,
        target_date=target.isoformat(),
        role=user.role,
        boat_id=boat_id,
    )
    focus = payload.get("focus_booking")
    return ShiftLiveResponse(
        date=target,
        focus_booking=BookingItem(**focus) if focus else None,  # type: ignore[arg-type]
    )
