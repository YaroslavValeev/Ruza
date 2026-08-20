from fastapi import APIRouter, Depends

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import UtmEventCreateRequest
from ..services.utm import create_utm_event


router = APIRouter(prefix="/utm-events", tags=["utm"])


@router.post("")
def post_utm_event(
    payload: UtmEventCreateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> dict[str, str]:
    return create_utm_event(sheet, payload, club_id=user.club_id)
