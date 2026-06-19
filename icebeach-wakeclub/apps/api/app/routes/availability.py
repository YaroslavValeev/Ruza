from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import AvailabilityItem
from ..services.availability import get_availability_for_date


router = APIRouter(tags=["availability"])


@router.get("/availability", response_model=list[AvailabilityItem])
def get_availability(
    date: str = Query(..., description="YYYY-MM-DD"),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot", "coach", "marketing_read")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[AvailabilityItem]:
    return get_availability_for_date(sheet, date, user.club_id)
