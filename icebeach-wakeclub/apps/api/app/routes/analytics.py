from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import AnalyticsSnapshotResponse
from ..services.analytics_snapshot import write_analytics_snapshot


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/snapshot", response_model=AnalyticsSnapshotResponse)
def post_analytics_snapshot(
    date_value: date = Query(..., alias="date"),
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> AnalyticsSnapshotResponse:
    result = write_analytics_snapshot(sheet, club_id=user.club_id, target_date=date_value.isoformat())
    return AnalyticsSnapshotResponse(**result)
