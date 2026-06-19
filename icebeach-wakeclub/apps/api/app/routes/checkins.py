from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import CheckinCreateRequest, CheckinItem, MarkLateResponse
from ..services.checkins import create_checkin, list_checkins, mark_late_checkins


router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.get("", response_model=list[CheckinItem])
def get_checkins(
    date_value: date = Query(..., alias="date"),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot", "coach")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[CheckinItem]:
    return [CheckinItem(**item) for item in list_checkins(sheet, club_id=user.club_id, target_date=date_value.isoformat())]


@router.post("", response_model=CheckinItem)
def post_checkin(
    payload: CheckinCreateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> CheckinItem:
    return CheckinItem(**create_checkin(sheet, payload, actor_staff_user_id=user.staff_user_id, club_id=user.club_id))


@router.post("/mark-late", response_model=MarkLateResponse)
def post_mark_late(
    date_value: date = Query(..., alias="date"),
    minutes_before: int = Query(default=10, ge=1, le=120),
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> MarkLateResponse:
    result = mark_late_checkins(
        sheet,
        club_id=user.club_id,
        target_date=date_value.isoformat(),
        actor_staff_user_id=user.staff_user_id,
        minutes_before=minutes_before,
    )
    return MarkLateResponse(**result)
