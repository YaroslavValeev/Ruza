from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import PilotQueueItem
from ..services.pilot import get_pilot_boat_id, get_pilot_queue


router = APIRouter(prefix="/pilot", tags=["pilot"])


@router.get("/today", response_model=list[PilotQueueItem])
def pilot_today(
    boat_id: str | None = Query(default=None),
    date: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[PilotQueueItem]:
    resolved_boat_id = boat_id
    if user.role == "pilot":
        assigned_boat = get_pilot_boat_id(sheet, staff_user_id=user.staff_user_id, club_id=user.club_id)
        if not assigned_boat:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="boat_id is required for this user")
        if resolved_boat_id and resolved_boat_id != assigned_boat:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pilot can only view assigned boat")
        resolved_boat_id = assigned_boat
    if not resolved_boat_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="boat_id is required for this user")
    if bool(date_from) != bool(date_to):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from and date_to must be provided together")
    return get_pilot_queue(
        sheet,
        boat_id=resolved_boat_id,
        club_id=user.club_id,
        target_date=date,
        date_from=date_from,
        date_to=date_to,
    )
