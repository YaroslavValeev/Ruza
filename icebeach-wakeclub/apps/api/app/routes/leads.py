from fastapi import APIRouter, Depends

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import LeadCreateRequest, LeadItem, LeadStatusUpdateRequest
from ..services.leads import create_lead, list_leads, update_lead_status


router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=list[LeadItem])
def get_leads(
    user: AuthUser = Depends(require_roles("admin", "operator", "marketing_read")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[LeadItem]:
    return [LeadItem(**item) for item in list_leads(sheet, club_id=user.club_id)]


@router.post("", response_model=LeadItem)
def post_lead(
    payload: LeadCreateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> LeadItem:
    return LeadItem(**create_lead(sheet, payload, actor_staff_user_id=user.staff_user_id, club_id=user.club_id))


@router.patch("/{lead_id}/status", response_model=LeadItem)
def patch_lead_status(
    lead_id: str,
    payload: LeadStatusUpdateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> LeadItem:
    return LeadItem(
        **update_lead_status(
            sheet,
            lead_id=lead_id,
            status_value=payload.status,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )
