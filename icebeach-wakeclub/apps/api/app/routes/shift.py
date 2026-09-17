from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import BookingItem, CheckinItem, ShiftSummary, ShiftTodayResponse
from ..services.shift import get_shift_today


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
