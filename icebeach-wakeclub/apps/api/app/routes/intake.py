from fastapi import APIRouter, Depends

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..config import Settings, get_settings
from ..dependencies import get_intake_sheet_wrapper, get_sheet_wrapper
from ..models import IntakeSyncResponse
from ..services.intake import sync_intake_leads


router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/sync", response_model=IntakeSyncResponse)
def sync_intake(
    user: AuthUser = Depends(require_roles("admin", "operator")),
    source_sheet: SheetWrapper = Depends(get_intake_sheet_wrapper),
    target_sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> IntakeSyncResponse:
    result = sync_intake_leads(
        source_sheet,
        target_sheet,
        source_tab=settings.intake_tab_name,
        club_id=user.club_id,
        actor=user.staff_user_id,
    )
    return IntakeSyncResponse(**result)
