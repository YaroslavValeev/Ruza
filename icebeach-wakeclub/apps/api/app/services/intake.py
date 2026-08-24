from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from packages.sheets import SheetWrapper

from ..models import PublicBookingRequest
from .common import normalize_phone


EXTERNAL_SOURCE = "mywave_canonical_ruza"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def lead_id_for_external(external_record_id: str) -> str:
    digest = hashlib.sha256(f"{EXTERNAL_SOURCE}:{external_record_id}".encode("utf-8")).hexdigest()[:24]
    return f"lead-intake-{digest}"


def create_canonical_booking_request(
    source_sheet: SheetWrapper,
    payload: PublicBookingRequest,
    *,
    source_tab: str,
) -> str:
    request_id = f"ruza-{uuid4()}"
    dedupe_payload = (
        f"{normalize_phone(payload.phone)}:{payload.date.isoformat()}:{payload.time}:"
        f"{payload.ride_type}:{request_id}"
    )
    source_sheet.append_row(
        source_tab,
        {
            "created_at": _utc_now_iso(),
            "request_id": request_id,
            "source_cta": "ruza_public_widget",
            "requester_role": "athlete",
            "parent_name": payload.full_name.strip(),
            "phone": normalize_phone(payload.phone),
            "goal": f"Катание за катером: {payload.ride_type}",
            "page_url": "/book",
            "status": "new",
            "status_updated_at": _utc_now_iso(),
            "dedupe_key": hashlib.sha256(dedupe_payload.encode("utf-8")).hexdigest(),
            "notes": (
                f"Желаемый слот: {payload.date.isoformat()} {payload.time}; "
                f"дисциплина: {payload.ride_type}. {payload.notes}"
            ).strip(),
        },
        unique_key="request_id",
    )
    return request_id


def _notes_from_source(row: dict[str, str]) -> str:
    fields = (
        ("Роль заявителя", "requester_role"),
        ("Спортсмен", "child_name"),
        ("Дата рождения", "birth_date"),
        ("Возрастная группа", "age_group"),
        ("Город", "city"),
        ("Уровень", "level"),
        ("Цель", "goal"),
        ("Пакет", "package"),
        ("Ограничения", "health_limits"),
        ("Детали ограничений", "health_details"),
        ("Логистика", "logistics"),
        ("Исходный статус", "status"),
        ("Страница", "page_url"),
        ("Примечание источника", "notes"),
    )
    return "; ".join(f"{label}: {row.get(key, '').strip()}" for label, key in fields if row.get(key, "").strip())


def sync_intake_leads(
    source_sheet: SheetWrapper,
    target_sheet: SheetWrapper,
    *,
    source_tab: str,
    club_id: str,
    actor: str,
) -> dict[str, object]:
    source_rows = source_sheet.read_tab(source_tab)
    existing_pairs = {
        (row.get("external_source", ""), row.get("external_record_id", ""))
        for row in target_sheet.read_tab("leads")
        if row.get("external_record_id")
    }
    result: dict[str, object] = {
        "source_tab": source_tab,
        "scanned": len(source_rows),
        "created": 0,
        "skipped_existing": 0,
        "skipped_invalid": 0,
        "errors": [],
    }

    for row_number, source_row in enumerate(source_rows, start=2):
        external_record_id = source_row.get("request_id", "").strip()
        full_name = (source_row.get("parent_name", "") or source_row.get("child_name", "")).strip()
        phone = normalize_phone(source_row.get("phone", ""))
        if not external_record_id or not full_name or len(phone) < 10:
            result["skipped_invalid"] = int(result["skipped_invalid"]) + 1
            continue

        pair = (EXTERNAL_SOURCE, external_record_id)
        if pair in existing_pairs:
            result["skipped_existing"] = int(result["skipped_existing"]) + 1
            continue

        lead_id = lead_id_for_external(external_record_id)
        lead_row = {
            "lead_id": lead_id,
            "club_id": club_id,
            "full_name": full_name,
            "phone": phone,
            "source": source_row.get("source_cta", "").strip() or EXTERNAL_SOURCE,
            "status": "new",
            "created_at": source_row.get("created_at", "").strip() or _utc_now_iso(),
            "external_source": EXTERNAL_SOURCE,
            "external_record_id": external_record_id,
            "utm_source": source_row.get("utm_source", "").strip(),
            "utm_campaign": source_row.get("utm_campaign", "").strip(),
            "notes": _notes_from_source(source_row),
        }
        try:
            target_sheet.append_row("leads", lead_row, unique_key="lead_id")
            target_sheet.write_audit(
                action="sync_create",
                entity="lead",
                entity_id=lead_id,
                diff_json={key: value for key, value in lead_row.items() if key != "phone"},
                actor=actor,
            )
        except Exception as exc:
            errors = result["errors"]
            assert isinstance(errors, list)
            errors.append(f"row {row_number}: {type(exc).__name__}")
            continue

        existing_pairs.add(pair)
        result["created"] = int(result["created"]) + 1

    return result
