from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import SmokeSummaryResponse
from ..services.smoke import run_smoke_check


router = APIRouter(prefix="/smoke", tags=["smoke"])


@router.post("/run", response_model=SmokeSummaryResponse)
def smoke_run(
    date: str = Query(..., description="Smoke date in YYYY-MM-DD format"),
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> SmokeSummaryResponse:
    return SmokeSummaryResponse(
        **run_smoke_check(
            sheet,
            target_date=date,
            club_id=user.club_id,
            actor_staff_user_id=user.staff_user_id,
        )
    )
