from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from ..models import PaymentCreateRequest, PaymentRefundRequest


PAYMENT_METHODS = ("cash", "card_terminal", "sbp", "online")
_PAYMENT_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_payment(row: dict[str, str]) -> dict[str, str | int]:
    return {
        "payment_id": row.get("payment_id", ""),
        "booking_id": row.get("booking_id", ""),
        "client_id": row.get("client_id", ""),
        "kind": row.get("kind", "charge"),
        "status": row.get("status", "succeeded"),
        "method": row.get("method", "cash"),
        "amount_minor": int(row.get("amount_minor") or 0),
        "currency": row.get("currency", "RUB"),
        "provider": row.get("provider", "manual"),
        "external_payment_id": row.get("external_payment_id", ""),
        "parent_payment_id": row.get("parent_payment_id", ""),
        "paid_at": row.get("paid_at") or row.get("occurred_at", ""),
        "occurred_at": row.get("occurred_at", ""),
        "recorded_by": row.get("recorded_by", ""),
    }


def _booking_for_club(sheet: SheetWrapper, booking_id: str, club_id: str) -> dict[str, str]:
    booking = next(
        (row for row in sheet.find("bookings", {"booking_id": booking_id}) if row.get("club_id") == club_id),
        None,
    )
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


def list_booking_payments(sheet: SheetWrapper, *, booking_id: str, club_id: str) -> list[dict[str, str | int]]:
    _booking_for_club(sheet, booking_id, club_id)
    rows = [
        row
        for row in sheet.read_tab("payments")
        if row.get("club_id") == club_id and row.get("booking_id") == booking_id
    ]
    rows.sort(key=lambda row: (row.get("occurred_at", ""), row.get("payment_id", "")))
    return [_serialize_payment(row) for row in rows]


def build_payment_summary(booking: dict[str, str], payments: list[dict[str, str]]) -> dict[str, str | int]:
    expected = int(booking.get("total_price") or 0) * 100
    succeeded = [row for row in payments if row.get("status") == "succeeded"]
    paid = sum(int(row.get("amount_minor") or 0) for row in succeeded if row.get("kind") == "charge")
    refunded = sum(int(row.get("amount_minor") or 0) for row in succeeded if row.get("kind") == "refund")
    net = paid - refunded
    balance = max(expected - net, 0)

    if paid == 0:
        payment_status = "unpaid"
    elif refunded >= paid:
        payment_status = "refunded"
    elif refunded > 0:
        payment_status = "partially_refunded"
    elif net < expected:
        payment_status = "partially_paid"
    elif net == expected:
        payment_status = "paid"
    else:
        payment_status = "overpaid"

    return {
        "booking_id": booking.get("booking_id", ""),
        "expected_amount_minor": expected,
        "paid_amount_minor": paid,
        "refunded_amount_minor": refunded,
        "net_paid_minor": net,
        "balance_due_minor": balance,
        "payment_status": payment_status,
    }


def payment_summaries_by_booking(
    bookings: list[dict[str, str]], payments: list[dict[str, str]]
) -> dict[str, dict[str, str | int]]:
    payments_by_booking: dict[str, list[dict[str, str]]] = {}
    for payment in payments:
        payments_by_booking.setdefault(payment.get("booking_id", ""), []).append(payment)
    return {
        booking.get("booking_id", ""): build_payment_summary(
            booking, payments_by_booking.get(booking.get("booking_id", ""), [])
        )
        for booking in bookings
    }


def get_booking_payment_summary(sheet: SheetWrapper, *, booking_id: str, club_id: str) -> dict[str, str | int]:
    booking = _booking_for_club(sheet, booking_id, club_id)
    payments = [
        row
        for row in sheet.read_tab("payments")
        if row.get("club_id") == club_id and row.get("booking_id") == booking_id
    ]
    return build_payment_summary(booking, payments)


def _find_idempotent(sheet: SheetWrapper, *, key: str, club_id: str, expected: dict[str, str]) -> dict[str, str] | None:
    existing = next(
        (row for row in sheet.find("payments", {"idempotency_key": key}) if row.get("club_id") == club_id),
        None,
    )
    if existing is None:
        return None
    comparable = ("booking_id", "kind", "method", "amount_minor", "parent_payment_id")
    if any(str(existing.get(field, "")) != str(expected.get(field, "")) for field in comparable):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key already used")
    return existing


def record_charge(
    sheet: SheetWrapper,
    payload: PaymentCreateRequest,
    *,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, object]:
    with _PAYMENT_LOCK:
        booking = _booking_for_club(sheet, payload.booking_id, club_id)
        expected = {
            "booking_id": payload.booking_id,
            "kind": "charge",
            "method": payload.method,
            "amount_minor": str(payload.amount_minor),
            "parent_payment_id": "",
        }
        existing = _find_idempotent(sheet, key=payload.idempotency_key, club_id=club_id, expected=expected)
        if existing is not None:
            return {
                "payment": _serialize_payment(existing),
                "summary": get_booking_payment_summary(sheet, booking_id=payload.booking_id, club_id=club_id),
            }

        now = _now_iso()
        occurred_at = payload.occurred_at or now
        row = {
            "payment_id": f"pay-{uuid4()}",
            "club_id": club_id,
            "booking_id": payload.booking_id,
            "client_id": booking.get("client_id", ""),
            "kind": "charge",
            "status": "succeeded",
            "method": payload.method,
            "amount_minor": payload.amount_minor,
            "currency": booking.get("currency") or "RUB",
            "paid_at": occurred_at,
            "provider": payload.provider,
            "external_payment_id": payload.external_payment_id,
            "idempotency_key": payload.idempotency_key,
            "parent_payment_id": "",
            "occurred_at": occurred_at,
            "recorded_by": actor_staff_user_id,
            "created_at": now,
            "metadata_json": "{}",
        }
        sheet.append_row("payments", row, unique_key="payment_id")
        sheet.write_audit(
            action="payment_recorded",
            entity="payment",
            entity_id=row["payment_id"],
            diff_json={key: value for key, value in row.items() if key != "metadata_json"},
            actor=actor_staff_user_id,
            strict=True,
        )
        return {
            "payment": _serialize_payment({key: str(value) for key, value in row.items()}),
            "summary": get_booking_payment_summary(sheet, booking_id=payload.booking_id, club_id=club_id),
        }


def record_refund(
    sheet: SheetWrapper,
    payment_id: str,
    payload: PaymentRefundRequest,
    *,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, object]:
    with _PAYMENT_LOCK:
        parent = next(
            (row for row in sheet.find("payments", {"payment_id": payment_id}) if row.get("club_id") == club_id),
            None,
        )
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if parent.get("kind") != "charge" or parent.get("status") != "succeeded":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only succeeded charges can be refunded")

        expected = {
            "booking_id": parent.get("booking_id", ""),
            "kind": "refund",
            "method": parent.get("method", "cash"),
            "amount_minor": str(payload.amount_minor),
            "parent_payment_id": payment_id,
        }
        existing = _find_idempotent(sheet, key=payload.idempotency_key, club_id=club_id, expected=expected)
        if existing is not None:
            return {
                "payment": _serialize_payment(existing),
                "summary": get_booking_payment_summary(
                    sheet, booking_id=parent.get("booking_id", ""), club_id=club_id
                ),
            }

        refunded = sum(
            int(row.get("amount_minor") or 0)
            for row in sheet.read_tab("payments")
            if row.get("club_id") == club_id
            and row.get("parent_payment_id") == payment_id
            and row.get("kind") == "refund"
            and row.get("status") == "succeeded"
        )
        if refunded + payload.amount_minor > int(parent.get("amount_minor") or 0):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Refund exceeds charge amount")

        now = _now_iso()
        occurred_at = payload.occurred_at or now
        row = {
            "payment_id": f"pay-{uuid4()}",
            "club_id": club_id,
            "booking_id": parent.get("booking_id", ""),
            "client_id": parent.get("client_id", ""),
            "kind": "refund",
            "status": "succeeded",
            "method": parent.get("method", "cash"),
            "amount_minor": payload.amount_minor,
            "currency": parent.get("currency") or "RUB",
            "paid_at": occurred_at,
            "provider": parent.get("provider") or "manual",
            "external_payment_id": "",
            "idempotency_key": payload.idempotency_key,
            "parent_payment_id": payment_id,
            "occurred_at": occurred_at,
            "recorded_by": actor_staff_user_id,
            "created_at": now,
            "metadata_json": json.dumps({"reason": "operator_refund"}, ensure_ascii=False),
        }
        sheet.append_row("payments", row, unique_key="payment_id")
        sheet.write_audit(
            action="payment_refunded",
            entity="payment",
            entity_id=row["payment_id"],
            diff_json={key: value for key, value in row.items() if key != "metadata_json"},
            actor=actor_staff_user_id,
            strict=True,
        )
        return {
            "payment": _serialize_payment({key: str(value) for key, value in row.items()}),
            "summary": get_booking_payment_summary(
                sheet, booking_id=parent.get("booking_id", ""), club_id=club_id
            ),
        }


def get_daily_reconciliation(sheet: SheetWrapper, *, target_date: str, club_id: str) -> dict[str, object]:
    bookings = [
        row
        for row in sheet.read_tab("bookings")
        if row.get("club_id") == club_id and row.get("date") == target_date
    ]
    booking_ids = {row.get("booking_id", "") for row in bookings}
    payments = [
        row
        for row in sheet.read_tab("payments")
        if row.get("club_id") == club_id
        and row.get("booking_id") in booking_ids
        and row.get("status") == "succeeded"
    ]
    active_bookings = [row for row in bookings if row.get("status") not in {"cancelled", "no_show"}]
    summaries = payment_summaries_by_booking(active_bookings, payments)
    charges = sum(int(row.get("amount_minor") or 0) for row in payments if row.get("kind") == "charge")
    refunds = sum(int(row.get("amount_minor") or 0) for row in payments if row.get("kind") == "refund")
    methods = []
    for method in PAYMENT_METHODS:
        method_charges = sum(
            int(row.get("amount_minor") or 0)
            for row in payments
            if row.get("kind") == "charge" and row.get("method") == method
        )
        method_refunds = sum(
            int(row.get("amount_minor") or 0)
            for row in payments
            if row.get("kind") == "refund" and row.get("method") == method
        )
        methods.append(
            {
                "method": method,
                "charges_minor": method_charges,
                "refunds_minor": method_refunds,
                "net_minor": method_charges - method_refunds,
            }
        )

    closure = next(
        (
            row
            for row in reversed(sheet.read_tab("payment_closures"))
            if row.get("club_id") == club_id and row.get("date") == target_date and row.get("status") == "closed"
        ),
        None,
    )
    return {
        "date": target_date,
        "bookings_value_minor": sum(int(row.get("total_price") or 0) * 100 for row in active_bookings),
        "completed_value_minor": sum(
            int(row.get("total_price") or 0) * 100 for row in active_bookings if row.get("status") == "done"
        ),
        "charges_minor": charges,
        "refunds_minor": refunds,
        "net_received_minor": charges - refunds,
        "outstanding_minor": sum(int(summary["balance_due_minor"]) for summary in summaries.values()),
        "methods": methods,
        "closure_status": "closed" if closure else "open",
        "discrepancy_minor": int(closure.get("discrepancy_minor") or 0) if closure else None,
    }


def close_daily_reconciliation(
    sheet: SheetWrapper,
    *,
    target_date: str,
    counted_total_minor: int,
    override_discrepancy: bool,
    notes: str,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, str | int]:
    with _PAYMENT_LOCK:
        existing = next(
            (
                row
                for row in sheet.read_tab("payment_closures")
                if row.get("club_id") == club_id and row.get("date") == target_date and row.get("status") == "closed"
            ),
            None,
        )
        if existing:
            return {
                "closure_id": existing.get("closure_id", ""),
                "date": existing.get("date", ""),
                "expected_net_minor": int(existing.get("expected_net_minor") or 0),
                "counted_total_minor": int(existing.get("counted_total_minor") or 0),
                "discrepancy_minor": int(existing.get("discrepancy_minor") or 0),
                "status": "closed",
                "closed_by": existing.get("closed_by", ""),
                "closed_at": existing.get("closed_at", ""),
            }

        summary = get_daily_reconciliation(sheet, target_date=target_date, club_id=club_id)
        expected = int(summary["net_received_minor"])
        discrepancy = counted_total_minor - expected
        if discrepancy and not override_discrepancy:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reconciliation discrepancy requires explicit override",
            )
        now = _now_iso()
        row = {
            "closure_id": f"close-{uuid4()}",
            "club_id": club_id,
            "date": target_date,
            "expected_net_minor": expected,
            "counted_total_minor": counted_total_minor,
            "discrepancy_minor": discrepancy,
            "status": "closed",
            "closed_by": actor_staff_user_id,
            "closed_at": now,
            "notes": notes,
        }
        sheet.append_row("payment_closures", row, unique_key="closure_id")
        sheet.write_audit(
            action="reconciliation_closed",
            entity="payment_closure",
            entity_id=row["closure_id"],
            diff_json=row,
            actor=actor_staff_user_id,
            strict=True,
        )
        return {key: value for key, value in row.items() if key not in {"club_id", "notes"}}
