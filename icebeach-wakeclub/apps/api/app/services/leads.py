from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from ..models import LeadCreateRequest, LeadStatus
from .common import normalize_phone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lead_to_item(row: dict[str, str]) -> dict[str, str]:
    return {
        "lead_id": row.get("lead_id", ""),
        "full_name": row.get("full_name", ""),
        "phone": row.get("phone", ""),
        "source": row.get("source", "offline"),
        "status": row.get("status", "new"),
        "utm_source": row.get("utm_source", ""),
        "utm_campaign": row.get("utm_campaign", ""),
        "created_at": row.get("created_at", ""),
        "notes": row.get("notes", ""),
        "external_source": row.get("external_source", ""),
        "external_record_id": row.get("external_record_id", ""),
        "received_at": row.get("received_at", ""),
        "sync_status": row.get("sync_status", ""),
        "sync_error": row.get("sync_error", ""),
        "converted_booking_id": row.get("converted_booking_id", ""),
    }


def list_leads(sheet: SheetWrapper, *, club_id: str) -> list[dict[str, str]]:
    rows = [row for row in sheet.read_tab("leads") if row.get("club_id") == club_id]
    rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
    return [_lead_to_item(row) for row in rows]


def create_lead(
    sheet: SheetWrapper,
    payload: LeadCreateRequest,
    *,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, str]:
    lead_id = f"lead-{uuid4()}"
    now = _utc_now_iso()
    row = {
        "lead_id": lead_id,
        "club_id": club_id,
        "full_name": payload.full_name.strip(),
        "phone": normalize_phone(payload.phone),
        "source": payload.source,
        "utm_source": payload.utm_source,
        "utm_campaign": payload.utm_campaign,
        "status": "new",
        "created_at": now,
        "notes": payload.notes,
        "external_source": "manual",
        "external_record_id": lead_id,
        "received_at": now,
        "sync_status": "manual",
        "sync_error": "",
        "converted_booking_id": "",
    }
    sheet.append_row("leads", row, unique_key="lead_id")
    sheet.write_audit(
        action="create",
        entity="lead",
        entity_id=lead_id,
        diff_json={key: value for key, value in row.items() if key != "phone"},
        actor=actor_staff_user_id,
    )
    return _lead_to_item(row)


def update_lead_status(
    sheet: SheetWrapper,
    *,
    lead_id: str,
    status_value: LeadStatus,
    actor_staff_user_id: str,
    club_id: str,
) -> dict[str, str]:
    rows = sheet.find("leads", {"lead_id": lead_id})
    row = next((item for item in rows if item.get("club_id") == club_id), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    patched = sheet.update_by_id(
        "leads",
        "lead_id",
        lead_id,
        {"status": status_value},
        actor=actor_staff_user_id,
        audit_entity="lead",
    )
    return _lead_to_item(patched)
