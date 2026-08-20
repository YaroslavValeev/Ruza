from fastapi import APIRouter, Depends

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import BoatItem
from ..services.common import parse_bool


router = APIRouter(prefix="/boats", tags=["boats"])


@router.get("", response_model=list[BoatItem])
def list_boats(
    user: AuthUser = Depends(require_roles("admin", "operator", "pilot")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[BoatItem]:
    rows = [
        row
        for row in sheet.read_tab("boats")
        if row.get("club_id") == user.club_id and parse_bool(row.get("is_active"))
    ]
    if user.role == "pilot":
        rows = [row for row in rows if row.get("pilot_user_id") == user.staff_user_id]
    rows.sort(key=lambda row: (row.get("boat_name", ""), row.get("boat_id", "")))
    return [
        BoatItem(
            boat_id=row.get("boat_id", ""),
            boat_name=row.get("boat_name") or row.get("boat_id", ""),
            capacity_default=int(row.get("capacity_default") or 1),
            pilot_user_id=row.get("pilot_user_id", ""),
            is_active=True,
        )
        for row in rows
        if row.get("boat_id")
    ]
