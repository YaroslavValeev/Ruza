from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import MarketingFunnelResponse
from ..services.marketing import get_marketing_funnel


router = APIRouter(prefix="/marketing", tags=["marketing"])


@router.get("/funnel", response_model=MarketingFunnelResponse)
def marketing_funnel(
    date_from: date = Query(...),
    date_to: date = Query(...),
    user: AuthUser = Depends(require_roles("admin", "operator", "marketing_read")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> MarketingFunnelResponse:
    result = get_marketing_funnel(
        sheet,
        club_id=user.club_id,
        period_from=date_from.isoformat(),
        period_to=date_to.isoformat(),
    )
    return MarketingFunnelResponse(**result)
