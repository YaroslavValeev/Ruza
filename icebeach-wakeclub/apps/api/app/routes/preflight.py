from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..config import Settings, get_settings
from ..dependencies import get_sheet_wrapper
from ..models import PreflightSummaryResponse
from ..services.preflight import run_preflight_check


router = APIRouter(prefix="/preflight", tags=["preflight"])


@router.get("/summary", response_model=PreflightSummaryResponse)
def preflight_summary(
    date: str = Query(..., description="Shift date in YYYY-MM-DD format"),
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> PreflightSummaryResponse:
    return PreflightSummaryResponse(
        **run_preflight_check(sheet, target_date=date, public_club_id=settings.public_club_id)
    )
