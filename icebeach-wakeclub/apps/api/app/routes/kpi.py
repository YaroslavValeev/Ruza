from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import KpiPeriod, KpiSummaryResponse
from ..services.kpi import get_kpi_summary


router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("/summary", response_model=KpiSummaryResponse)
def kpi_summary(
    period: KpiPeriod = Query(default="day"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot", "coach", "marketing_read")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> KpiSummaryResponse:
    return KpiSummaryResponse(**get_kpi_summary(sheet, user.club_id, period=period, date_from=date_from, date_to=date_to))
