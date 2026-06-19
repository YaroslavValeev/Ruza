from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from packages.sheets import SheetWrapper

from .common import normalize_phone


def list_clients(sheet: SheetWrapper, club_id: str, query: str = "") -> list[dict[str, str | bool]]:
    normalized_query = query.strip().lower()
    normalized_phone_query = normalize_phone(query)
    rows = [row for row in sheet.read_tab("clients") if row.get("club_id") == club_id]

    result: list[dict[str, str | bool]] = []
    for row in rows:
        full_name = row.get("full_name", "")
        phone = row.get("phone", "")
        if normalized_query:
            haystacks = (full_name.lower(), row.get("client_id", "").lower(), normalize_phone(phone))
            if not (
                normalized_query in haystacks[0]
                or normalized_query in haystacks[1]
                or (normalized_phone_query and normalized_phone_query in haystacks[2])
            ):
                continue

        result.append(
            {
                "client_id": row.get("client_id", ""),
                "full_name": full_name,
                "phone": phone,
                "consent_face": str(row.get("consent_face", "")).lower() in {"1", "true", "yes"},
                "consent_voice": str(row.get("consent_voice", "")).lower() in {"1", "true", "yes"},
            }
        )

    result.sort(key=lambda item: str(item["full_name"]).lower())
    return result


def create_client(
    sheet: SheetWrapper,
    *,
    club_id: str,
    full_name: str,
    phone: str,
    consent_face: bool,
    consent_voice: bool,
    actor: str,
) -> dict[str, str | bool]:
    normalized_phone = normalize_phone(phone)
    existing = [
        row
        for row in sheet.read_tab("clients")
        if row.get("club_id") == club_id and normalize_phone(row.get("phone", "")) == normalized_phone
    ]
    if existing:
        row = existing[0]
        return {
            "client_id": row.get("client_id", ""),
            "full_name": row.get("full_name", ""),
            "phone": row.get("phone", ""),
            "consent_face": str(row.get("consent_face", "")).lower() in {"1", "true", "yes"},
            "consent_voice": str(row.get("consent_voice", "")).lower() in {"1", "true", "yes"},
        }

    client_id = f"client-{uuid4()}"
    created_at = datetime.now(timezone.utc).isoformat()
    row = {
        "client_id": client_id,
        "club_id": club_id,
        "full_name": full_name.strip(),
        "phone": phone.strip(),
        "consent_face": consent_face,
        "consent_voice": consent_voice,
        "created_at": created_at,
    }
    sheet.append_row("clients", row, unique_key="client_id")
    sheet.write_audit(
        action="create",
        entity="client",
        entity_id=client_id,
        diff_json=row,
        actor=actor,
    )
    return {
        "client_id": client_id,
        "full_name": full_name.strip(),
        "phone": phone.strip(),
        "consent_face": consent_face,
        "consent_voice": consent_voice,
    }

