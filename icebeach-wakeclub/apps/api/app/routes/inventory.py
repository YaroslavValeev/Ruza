from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import (
    BoardCreateRequest,
    BoardRef,
    BoardUpdateRequest,
    WetsuitCreateRequest,
    WetsuitRef,
    WetsuitUpdateRequest,
)
from ..services.equipment import create_inventory_item, list_inventory, update_inventory_item


router = APIRouter(prefix="/inventory", tags=["inventory"])

READ_ROLES = ("admin", "operator", "coach", "pilot")


@router.get("/boards", response_model=list[BoardRef])
def get_boards(
    include_inactive: bool = Query(default=False),
    user: AuthUser = Depends(require_roles(*READ_ROLES)),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[BoardRef]:
    show_inactive = include_inactive and user.role == "admin"
    return [BoardRef(**item) for item in list_inventory(sheet, tab="boards", club_id=user.club_id, include_inactive=show_inactive)]


@router.post("/boards", response_model=BoardRef)
def post_board(
    payload: BoardCreateRequest,
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> BoardRef:
    item = create_inventory_item(sheet, tab="boards", club_id=user.club_id, fields=payload.model_dump(), actor=user.staff_user_id)
    return BoardRef(**item)


@router.patch("/boards/{board_id}", response_model=BoardRef)
def patch_board(
    board_id: str,
    payload: BoardUpdateRequest,
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> BoardRef:
    item = update_inventory_item(
        sheet,
        tab="boards",
        club_id=user.club_id,
        item_id=board_id,
        fields=payload.model_dump(exclude_unset=True),
        actor=user.staff_user_id,
    )
    return BoardRef(**item)


@router.get("/wetsuits", response_model=list[WetsuitRef])
def get_wetsuits(
    include_inactive: bool = Query(default=False),
    user: AuthUser = Depends(require_roles(*READ_ROLES)),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[WetsuitRef]:
    show_inactive = include_inactive and user.role == "admin"
    return [WetsuitRef(**item) for item in list_inventory(sheet, tab="wetsuits", club_id=user.club_id, include_inactive=show_inactive)]


@router.post("/wetsuits", response_model=WetsuitRef)
def post_wetsuit(
    payload: WetsuitCreateRequest,
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> WetsuitRef:
    item = create_inventory_item(sheet, tab="wetsuits", club_id=user.club_id, fields=payload.model_dump(), actor=user.staff_user_id)
    return WetsuitRef(**item)


@router.patch("/wetsuits/{wetsuit_id}", response_model=WetsuitRef)
def patch_wetsuit(
    wetsuit_id: str,
    payload: WetsuitUpdateRequest,
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> WetsuitRef:
    item = update_inventory_item(
        sheet,
        tab="wetsuits",
        club_id=user.club_id,
        item_id=wetsuit_id,
        fields=payload.model_dump(exclude_unset=True),
        actor=user.staff_user_id,
    )
    return WetsuitRef(**item)
