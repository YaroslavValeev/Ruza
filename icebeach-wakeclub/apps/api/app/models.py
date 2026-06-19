from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


StaffRole = Literal["admin", "operator", "pilot", "coach", "marketing_read"]
BookingStatus = Literal["confirmed", "arrived", "ready", "in_progress", "done", "late", "no_show", "cancelled"]
WetsuitSize = Literal["XS", "S", "M", "L", "XL", "XXL"]
WetsuitGender = Literal["male", "female"]
RideType = Literal["wakeboard", "surf", "skim"]
KpiPeriod = Literal["day", "week", "month", "season", "custom"]
PreflightLevel = Literal["PASS", "WARN", "BLOCKER"]
SmokeLevel = Literal["PASS", "FAIL"]


class LoginRequest(BaseModel):
    staff_user_id: str = Field(min_length=1)


class LoginCodeRequest(BaseModel):
    staff_user_id: str = Field(min_length=1)
    phone: str = Field(min_length=5)


class LoginCodeResponse(BaseModel):
    delivery_channel: str
    expires_in_seconds: int
    debug_code: str | None = None


class LoginVerifyRequest(BaseModel):
    staff_user_id: str = Field(min_length=1)
    code: str = Field(min_length=4, max_length=8)


class SessionResponse(BaseModel):
    staff_user_id: str
    role: StaffRole
    full_name: str
    club_id: str
    phone: str = ""
    boat_id: str | None = None


class AvailabilityItem(BaseModel):
    date: date
    time: str
    boat_id: str
    capacity: int
    booked: int
    available: int
    status: str


class BookingCreateRequest(BaseModel):
    booking_id: str | None = None
    client_id: str
    date: date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    boat_id: str
    coach_required: bool = False
    coach_user_id: str | None = None
    ride_type: RideType = "wakeboard"
    wetsuit_required: bool = False
    wetsuit_size: WetsuitSize | None = None
    wetsuit_gender: WetsuitGender | None = None
    discount: int = 0
    notes: str = ""

    @model_validator(mode="after")
    def validate_wetsuit(self) -> "BookingCreateRequest":
        if self.wetsuit_required and not self.wetsuit_size:
            raise ValueError("wetsuit_size is required when wetsuit_required=true")
        if self.wetsuit_required and not self.wetsuit_gender:
            raise ValueError("wetsuit_gender is required when wetsuit_required=true")
        if not self.wetsuit_required:
            self.wetsuit_size = None
            self.wetsuit_gender = None
        return self


class BookingCreateResponse(BaseModel):
    booking_id: str
    status: BookingStatus
    total_price: int


class BookingItem(BaseModel):
    booking_id: str
    client_id: str
    client_name: str = ""
    client_phone: str = ""
    date: date
    time: str
    boat_id: str
    status: BookingStatus
    coach_required: bool
    coach_user_id: str | None = None
    ride_type: RideType = "wakeboard"
    wetsuit_required: bool = False
    wetsuit_size: WetsuitSize | None = None
    wetsuit_gender: WetsuitGender | None = None
    total_price: int
    notes: str = ""


class BookingStatusUpdateRequest(BaseModel):
    status: BookingStatus


class ClientItem(BaseModel):
    client_id: str
    full_name: str
    phone: str
    consent_face: bool = False
    consent_voice: bool = False


class ClientCreateRequest(BaseModel):
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=5)
    consent_face: bool = False
    consent_voice: bool = False


class PilotQueueItem(BaseModel):
    booking_id: str
    date: date
    time: str
    boat_id: str
    client_id: str
    client_name: str = ""
    status: BookingStatus
    coach_required: bool
    ride_type: RideType = "wakeboard"


class KpiRideBreakdownItem(BaseModel):
    ride_type: RideType
    sessions_count: int
    revenue_estimate: int


class KpiTimelinePoint(BaseModel):
    date: date
    sessions_count: int
    revenue_estimate: int
    utilization_pct: float


class PreflightCheckItem(BaseModel):
    level: PreflightLevel
    code: str
    message: str


class PreflightSummaryResponse(BaseModel):
    target_date: date
    blockers: int
    warnings: int
    checks: list[PreflightCheckItem]


class SmokeCheckItem(BaseModel):
    level: SmokeLevel
    code: str
    message: str


class SmokeSummaryResponse(BaseModel):
    target_date: date
    ok: bool
    created_booking_id: str | None = None
    selected_client_id: str | None = None
    selected_slot: str | None = None
    checks: list[SmokeCheckItem]


CheckinMethod = Literal["phone", "manual", "face", "system"]
CheckinStatus = Literal["arrived", "ready", "late", "cancelled"]
LeadStatus = Literal["new", "contacted", "booked", "lost"]


class CheckinCreateRequest(BaseModel):
    method: CheckinMethod
    date: date
    phone: str | None = None
    client_id: str | None = None
    booking_id: str | None = None
    status: CheckinStatus = "arrived"


class CheckinItem(BaseModel):
    checkin_id: str
    club_id: str
    booking_id: str
    client_id: str
    method: CheckinMethod
    status: CheckinStatus
    ts: str
    operator_user_id: str | None = None


class MarkLateResponse(BaseModel):
    marked_late: int


class KpiPlanFact(BaseModel):
    sessions_target: int | None = None
    utilization_target_pct: int | None = None
    revenue_target: int | None = None
    sessions_pct: float | None = None
    utilization_pct_of_target: float | None = None
    revenue_pct: float | None = None


class KpiSummaryResponse(BaseModel):
    period: KpiPeriod
    date_from: date
    date_to: date
    sessions_count: int
    utilization_pct: float
    revenue_estimate: int
    ride_breakdown: list[KpiRideBreakdownItem]
    timeline: list[KpiTimelinePoint]
    plan_fact: KpiPlanFact | None = None


class AnalyticsSnapshotResponse(BaseModel):
    date: date
    club_id: str
    sessions_count: int
    utilization_pct: float
    revenue_estimate: int
    no_show_rate: float
    written: bool


class LeadItem(BaseModel):
    lead_id: str
    full_name: str
    phone: str
    source: str
    status: LeadStatus
    utm_source: str = ""
    utm_campaign: str = ""
    created_at: str
    notes: str = ""


class LeadCreateRequest(BaseModel):
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=5)
    source: str = "offline"
    utm_source: str = ""
    utm_campaign: str = ""
    notes: str = ""


class LeadStatusUpdateRequest(BaseModel):
    status: LeadStatus


class MarketingFunnelResponse(BaseModel):
    period_from: date
    period_to: date
    leads_count: int
    contacted_count: int
    booked_count: int
    lost_count: int
    conversion_to_booked_pct: float
    cac_estimate: int | None = None


class UtmEventCreateRequest(BaseModel):
    event_type: str = Field(min_length=1)
    utm_source: str = ""
    utm_campaign: str = ""
    page: str = ""
    anon_id: str = ""

