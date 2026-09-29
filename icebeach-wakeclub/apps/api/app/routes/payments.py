from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..auth import AuthUser, require_roles
from ..dependencies import get_sheet_wrapper
from ..models import (
    BookingPaymentSummary,
    DailyReconciliationResponse,
    PaymentCreateRequest,
    PaymentItem,
    PaymentMutationResponse,
    PaymentRefundRequest,
    ReconciliationCloseRequest,
    ReconciliationClosureItem,
)
from ..services.payments import (
    close_daily_reconciliation,
    get_booking_payment_summary,
    get_daily_reconciliation,
    list_booking_payments,
    record_charge,
    record_refund,
)


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentMutationResponse)
def post_payment(
    payload: PaymentCreateRequest,
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> PaymentMutationResponse:
    return PaymentMutationResponse(
        **record_charge(
            sheet,
            payload,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )


@router.get("", response_model=list[PaymentItem])
def get_payments(
    booking_id: str = Query(...),
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> list[PaymentItem]:
    return [PaymentItem(**item) for item in list_booking_payments(sheet, booking_id=booking_id, club_id=user.club_id)]


@router.get("/summary", response_model=BookingPaymentSummary)
def get_payment_summary(
    booking_id: str = Query(...),
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> BookingPaymentSummary:
    return BookingPaymentSummary(**get_booking_payment_summary(sheet, booking_id=booking_id, club_id=user.club_id))


@router.post("/{payment_id}/refunds", response_model=PaymentMutationResponse)
def post_refund(
    payment_id: str,
    payload: PaymentRefundRequest,
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> PaymentMutationResponse:
    return PaymentMutationResponse(
        **record_refund(
            sheet,
            payment_id,
            payload,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )


@router.get("/reconciliation/daily", response_model=DailyReconciliationResponse)
def get_reconciliation(
    date_value: date = Query(..., alias="date"),
    user: AuthUser = Depends(require_roles("admin", "operator")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> DailyReconciliationResponse:
    return DailyReconciliationResponse(
        **get_daily_reconciliation(sheet, target_date=date_value.isoformat(), club_id=user.club_id)
    )


@router.post("/reconciliation/close", response_model=ReconciliationClosureItem)
def post_reconciliation_close(
    payload: ReconciliationCloseRequest,
    user: AuthUser = Depends(require_roles("admin")),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> ReconciliationClosureItem:
    return ReconciliationClosureItem(
        **close_daily_reconciliation(
            sheet,
            target_date=payload.date.isoformat(),
            counted_total_minor=payload.counted_total_minor,
            override_discrepancy=payload.override_discrepancy,
            notes=payload.notes,
            actor_staff_user_id=user.staff_user_id,
            club_id=user.club_id,
        )
    )
