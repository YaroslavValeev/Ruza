from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str


class LoginRequest(BaseModel):
    phone: str


class LoginResponse(BaseModel):
    token: str
    role: str
    staff_user_id: str


class BookingCreateRequest(BaseModel):
    client_id: str
    date: str
    time: str
    boat_id: str
    coach_required: bool = False
    coach_user_id: str | None = None
    price_base: float = Field(ge=0)
    price_coach: float = Field(default=0, ge=0)


class BookingCreateResponse(BaseModel):
    booking_id: str
    status: str
    total_price: float
    idempotent_replay: bool = False


class CheckinCreateRequest(BaseModel):
    booking_id: str
    method: str
    status: str


class BookingStatusPatchRequest(BaseModel):
    status: str
