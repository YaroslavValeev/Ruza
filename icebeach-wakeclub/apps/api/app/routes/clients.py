from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import ClientCreateRequest, ClientItem
from ..services.clients import create_client, list_clients


router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientItem])
def get_clients(
    query: str = Query(default=""),
    user: AuthUser = Depends(require_roles("admin", "operator", "coach")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[ClientItem]:
    return [ClientItem(**item) for item in list_clients(sheet, user.club_id, query)]


@router.post("", response_model=ClientItem)
def post_client(
    payload: ClientCreateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> ClientItem:
    item = create_client(
        sheet,
        club_id=user.club_id,
        full_name=payload.full_name,
        phone=payload.phone,
        consent_face=payload.consent_face,
        consent_voice=payload.consent_voice,
        actor=user.staff_user_id,
    )
    return ClientItem(**item)
