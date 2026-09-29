from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "icebeach-wakeclub"
API_DIR = REPO_ROOT / "apps" / "api"

os.chdir(API_DIR)
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings
from app.services.common import normalize_phone
from app.services.intake import EXTERNAL_SOURCE, lead_id_for_external, sync_intake_leads
from packages.sheets import SheetWrapper


SOURCE_REQUIRED_COLUMNS = (
    "created_at",
    "request_id",
    "source_cta",
    "requester_role",
    "parent_name",
    "phone",
    "goal",
    "status",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pass(code: str, message: str) -> None:
    print(f"[PASS] {code}: {message}")


def _fail(code: str, message: str) -> None:
    print(f"[FAIL] {code}: {message}")
    raise SystemExit(1)


def _build_phone(external_record_id: str) -> str:
    digest = hashlib.sha256(external_record_id.encode("utf-8")).hexdigest()
    suffix = str(int(digest[:8], 16) % 1000000).zfill(6)
    return f"+7999{suffix}"


def _source_headers(sheet: SheetWrapper, source_tab: str) -> list[str]:
    values = sheet._fetch_values(source_tab)  # noqa: SLF001
    if not values or not values[0]:
        _fail("intake.headers", f"source tab '{source_tab}' has no header row")
    return list(values[0])


def _matching_leads(sheet: SheetWrapper, external_record_id: str) -> list[dict[str, str]]:
    return [
        row
        for row in sheet.read_tab("leads")
        if row.get("external_source") == EXTERNAL_SOURCE and row.get("external_record_id") == external_record_id
    ]


def _ensure_source_row(
    sheet: SheetWrapper,
    *,
    source_tab: str,
    external_record_id: str,
    phone: str,
    full_name: str,
) -> str:
    headers = _source_headers(sheet, source_tab)
    missing = [column for column in SOURCE_REQUIRED_COLUMNS if column not in headers]
    if missing:
        _fail("intake.headers", f"source tab '{source_tab}' missing columns: {', '.join(missing)}")

    existing = sheet.find(source_tab, {"request_id": external_record_id})
    if existing:
        _pass("source.row", f"existing request_id={external_record_id}")
        return "existing"

    now = _utc_now_iso()
    sheet.append_row(
        source_tab,
        {
            "created_at": now,
            "request_id": external_record_id,
            "source_cta": "smoke_intake_e2e",
            "requester_role": "athlete",
            "parent_name": full_name,
            "phone": normalize_phone(phone),
            "goal": "Тестовая заявка: катание за катером",
            "page_url": "/smoke/intake-e2e",
            "status": "new",
            "status_updated_at": now,
            "dedupe_key": hashlib.sha256(f"{external_record_id}:{normalize_phone(phone)}".encode("utf-8")).hexdigest(),
            "utm_source": "codex_local_e2e",
            "utm_campaign": "production_v1_gate",
            "notes": "E2E proof row. Safe to keep; repeated sync must not duplicate.",
        },
        unique_key="request_id",
    )
    _pass("source.row", f"created request_id={external_record_id}")
    return "created"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live local intake idempotency proof for Ruza production v1 gate")
    parser.add_argument(
        "--external-record-id",
        default=f"smoke-intake-e2e-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        help="Stable request_id to prove sync idempotency. Default is one deterministic row per UTC day.",
    )
    parser.add_argument("--full-name", default="Smoke Intake E2E", help="Test lead name written to the intake source")
    parser.add_argument("--phone", default="", help="Optional test phone. If omitted, a deterministic phone is generated.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    if not settings.intake_spreadsheet_id:
        _fail("env.intake_spreadsheet_id", "INTAKE_SPREADSHEET_ID is not configured")

    phone = args.phone.strip() or _build_phone(args.external_record_id)
    source_sheet = SheetWrapper(
        settings.intake_spreadsheet_id,
        service_account_json_path=settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )
    target_sheet = SheetWrapper(
        settings.spreadsheet_id,
        service_account_json_path=settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )

    _pass("config.source_tab", settings.intake_tab_name)
    _pass("config.club_id", settings.public_club_id)
    _ensure_source_row(
        source_sheet,
        source_tab=settings.intake_tab_name,
        external_record_id=args.external_record_id,
        phone=phone,
        full_name=args.full_name,
    )

    before = _matching_leads(target_sheet, args.external_record_id)
    if len(before) > 1:
        _fail("target.leads.before", f"duplicate leads before sync: {len(before)}")
    _pass("target.leads.before", str(len(before)))

    first = sync_intake_leads(
        source_sheet,
        target_sheet,
        source_tab=settings.intake_tab_name,
        club_id=settings.public_club_id,
        actor=settings.agents_staff_user_id,
    )
    if first["errors"]:
        _fail("sync.first", f"errors={first['errors']}")
    if before and int(first["created"]) != 0:
        _fail("sync.first", f"expected created=0 for existing lead, got {first['created']}")
    if not before and int(first["created"]) < 1:
        _fail("sync.first", f"expected created>=1 for new lead, got {first['created']}")
    _pass("sync.first", f"created={first['created']} skipped_existing={first['skipped_existing']}")

    second = sync_intake_leads(
        source_sheet,
        target_sheet,
        source_tab=settings.intake_tab_name,
        club_id=settings.public_club_id,
        actor=settings.agents_staff_user_id,
    )
    if second["errors"]:
        _fail("sync.second", f"errors={second['errors']}")
    if int(second["created"]) != 0:
        _fail("sync.second", f"expected created=0, got {second['created']}")
    if int(second["skipped_existing"]) < 1:
        _fail("sync.second", f"expected skipped_existing>=1, got {second['skipped_existing']}")
    _pass("sync.second", f"created={second['created']} skipped_existing={second['skipped_existing']}")

    after = _matching_leads(target_sheet, args.external_record_id)
    if len(after) != 1:
        _fail("target.leads.after", f"expected exactly 1 lead, got {len(after)}")
    lead = after[0]
    expected_lead_id = lead_id_for_external(args.external_record_id)
    if lead.get("lead_id") != expected_lead_id:
        _fail("target.lead_id", f"expected {expected_lead_id}, got {lead.get('lead_id')}")
    if lead.get("sync_status") != "synced":
        _fail("target.sync_status", f"expected synced, got {lead.get('sync_status')}")
    _pass("target.leads.after", f"lead_id={lead['lead_id']} sync_status={lead['sync_status']}")

    print("SUMMARY failures=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
