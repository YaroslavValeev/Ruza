"""Schema contract for Google Sheets tabs used by the system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TabSchema:
    name: str
    required_columns: tuple[str, ...]


TAB_SCHEMAS: dict[str, TabSchema] = {
    "clubs": TabSchema("clubs", ("club_id", "club_name", "timezone", "is_active")),
    "boats": TabSchema(
        "boats",
        ("boat_id", "club_id", "boat_name", "capacity_default", "pilot_user_id", "is_active"),
    ),
    "staff_users": TabSchema(
        "staff_users",
        ("staff_user_id", "club_id", "role", "full_name", "phone", "is_active", "created_at"),
    ),
    "pricing": TabSchema(
        "pricing",
        ("price_id", "club_id", "valid_from", "base_price", "coach_price", "currency"),
    ),
    "clients": TabSchema(
        "clients",
        ("client_id", "club_id", "full_name", "phone", "consent_face", "consent_voice", "created_at"),
    ),
    "schedule": TabSchema(
        "schedule",
        ("schedule_id", "club_id", "weekday", "time", "boat_id", "capacity", "is_active"),
    ),
    "slot_overrides": TabSchema(
        "slot_overrides",
        ("slot_id", "club_id", "date", "time", "boat_id", "capacity", "status"),
    ),
    "bookings": TabSchema(
        "bookings",
        (
            "booking_id",
            "club_id",
            "client_id",
            "date",
            "time",
            "boat_id",
            "status",
            "pricing_id",
            "price_base",
            "price_coach",
            "discount",
            "currency",
            "total_price",
            "created_by",
            "created_at",
            "updated_at",
            "coach_required",
            "coach_user_id",
            "ride_type",
            "wetsuit_required",
            "wetsuit_size",
            "wetsuit_gender",
            "notes",
        ),
    ),
    "analytics_daily": TabSchema(
        "analytics_daily",
        ("date", "club_id", "sessions_count", "utilization_pct", "revenue_estimate"),
    ),
    "auth_codes": TabSchema(
        "auth_codes",
        ("auth_code_id", "staff_user_id", "club_id", "code_hash", "created_at", "expires_at", "used_at", "delivery_channel"),
    ),
    "audit_log": TabSchema(
        "audit_log",
        ("ts", "actor", "action", "entity", "entity_id", "diff_json"),
    ),
    "checkins": TabSchema(
        "checkins",
        ("checkin_id", "club_id", "booking_id", "client_id", "method", "status", "ts", "operator_user_id"),
    ),
    "kpi_targets": TabSchema(
        "kpi_targets",
        ("target_id", "club_id", "period", "sessions_target", "utilization_target_pct", "revenue_target"),
    ),
    "leads": TabSchema(
        "leads",
        (
            "lead_id",
            "club_id",
            "full_name",
            "phone",
            "source",
            "status",
            "created_at",
            "external_source",
            "external_record_id",
            "received_at",
            "sync_status",
            "sync_error",
            "converted_booking_id",
            "utm_source",
            "utm_campaign",
            "notes",
        ),
    ),
    "payments": TabSchema(
        "payments",
        (
            "payment_id",
            "club_id",
            "booking_id",
            "client_id",
            "kind",
            "status",
            "method",
            "amount_minor",
            "currency",
            "paid_at",
            "provider",
            "external_payment_id",
            "idempotency_key",
            "parent_payment_id",
            "occurred_at",
            "recorded_by",
            "created_at",
            "metadata_json",
        ),
    ),
    "payment_closures": TabSchema(
        "payment_closures",
        (
            "closure_id",
            "club_id",
            "date",
            "expected_net_minor",
            "counted_total_minor",
            "discrepancy_minor",
            "status",
            "closed_by",
            "closed_at",
            "notes",
        ),
    ),
    "campaigns": TabSchema(
        "campaigns",
        ("campaign_id", "club_id", "name", "channel", "start_date", "budget"),
    ),
    "utm_events": TabSchema(
        "utm_events",
        ("event_id", "club_id", "ts", "event_type", "utm_source", "utm_campaign"),
    ),
}


def validate_required_columns(tab_name: str, headers: list[str]) -> None:
    schema = TAB_SCHEMAS.get(tab_name)
    if not schema:
        return

    missing = [col for col in schema.required_columns if col not in headers]
    if missing:
        raise ValueError(f"Tab '{tab_name}' is missing required columns: {', '.join(missing)}")
