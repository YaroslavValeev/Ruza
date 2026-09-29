from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import ApprovalRequestCreate, ApprovalRequestItem


router = APIRouter(prefix="/approvals", tags=["approvals"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/request", response_model=ApprovalRequestItem)
def create_approval_request(
    payload: ApprovalRequestCreate,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> ApprovalRequestItem:
    approval_id = f"apr-{uuid4()}"
    row = {
        "approval_id": approval_id,
        "action": payload.action,
        "entity": payload.entity,
        "entity_id": payload.entity_id,
        "status": "pending",
        "reason": payload.reason,
        "requested_by": user.staff_user_id,
        "created_at": _utc_now_iso(),
    }
    sheet.write_audit(
        action="approval_request",
        entity=payload.entity,
        entity_id=payload.entity_id,
        diff_json=row,
        actor=user.staff_user_id,
    )
    return ApprovalRequestItem(
        approval_id=approval_id,
        action=payload.action,
        entity=payload.entity,
        entity_id=payload.entity_id,
        status="pending",
        reason=payload.reason,
        created_at=row["created_at"],
    )


@router.post("/{approval_id}/decide", response_model=ApprovalRequestItem)
def decide_approval(
    approval_id: str,
    decision: str = Query(..., pattern="^(approved|rejected)$"),
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> ApprovalRequestItem:
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be approved or rejected")

    row = {
        "approval_id": approval_id,
        "status": decision,
        "decided_by": user.staff_user_id,
        "decided_at": _utc_now_iso(),
    }
    sheet.write_audit(
        action=f"approval_{decision}",
        entity="approval",
        entity_id=approval_id,
        diff_json=row,
        actor=user.staff_user_id,
    )
    return ApprovalRequestItem(
        approval_id=approval_id,
        action="",
        entity="approval",
        entity_id=approval_id,
        status=decision,  # type: ignore[arg-type]
        created_at=row["decided_at"],
    )
