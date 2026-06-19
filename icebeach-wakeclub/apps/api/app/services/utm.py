from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from packages.sheets import SheetWrapper

from ..models import UtmEventCreateRequest


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_utm_event(
    sheet: SheetWrapper,
    payload: UtmEventCreateRequest,
    *,
    club_id: str,
) -> dict[str, str]:
    event_id = f"utm-{uuid4()}"
    row = {
        "event_id": event_id,
        "club_id": club_id,
        "ts": _utc_now_iso(),
        "event_type": payload.event_type,
        "utm_source": payload.utm_source,
        "utm_campaign": payload.utm_campaign,
        "page": payload.page,
        "anon_id": payload.anon_id,
    }
    sheet.append_row("utm_events", row, unique_key="event_id")
    return row
