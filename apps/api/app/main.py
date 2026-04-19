from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .errors import ApiError
from .models import (
    BookingCreateRequest,
    BookingCreateResponse,
    BookingStatusPatchRequest,
    CheckinCreateRequest,
    LoginRequest,
    LoginResponse,
)
from .security import create_session_token, has_permission, parse_session_token
from .services_ops import (
    build_availability,
    create_booking,
    create_checkin,
    diagnostics_snapshot,
    get_pilot_queue,
    kpi_drilldown,
    kpi_view,
    update_booking_status,
)
from .sheets_provider import get_sheets

app = FastAPI(title="Ice Beach API", version="0.3.0")

cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(ApiError)
async def api_error_handler(_, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


def current_session(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise ApiError(status_code=401, code="UNAUTHORIZED", message="Missing Bearer token")
    token = authorization.replace("Bearer ", "", 1)
    try:
        return parse_session_token(token)
    except ValueError as exc:
        raise ApiError(status_code=401, code="UNAUTHORIZED", message=str(exc)) from exc


def require_permission(permission: str):
    def checker(session: dict = Depends(current_session)) -> dict:
        role = session.get("role", "")
        if not has_permission(role, permission):
            raise ApiError(status_code=403, code="FORBIDDEN", message="Forbidden by RBAC")
        return session

    return checker


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, sheets=Depends(get_sheets)) -> LoginResponse:
    staff = sheets.find("staff_users", lambda row: row.get("phone") == payload.phone)
    if not staff:
        raise ApiError(status_code=401, code="UNAUTHORIZED", message="Unknown phone")
    user = staff[0]
    token = create_session_token(staff_user_id=user["staff_user_id"], role=user["role"])
    return LoginResponse(token=token, role=user["role"], staff_user_id=user["staff_user_id"])


@app.get("/admin/ping")
def admin_ping(_: dict = Depends(require_permission("write:admin"))) -> dict:
    return {"ok": True}


@app.post("/ops/audit-test")
def audit_test(session: dict = Depends(require_permission("write:ops")), sheets=Depends(get_sheets)):
    sheets.write_audit(
        action="create",
        entity="audit_test",
        entity_id=session["staff_user_id"],
        diff_json={"message": "week1 smoke"},
        actor=session["staff_user_id"],
    )
    return {"ok": True}


@app.get("/ops/schema-check")
def schema_check(_: dict = Depends(require_permission("read:ops")), sheets=Depends(get_sheets)):
    required = {
        "staff_users": ["staff_user_id", "phone", "role"],
        "bookings": ["booking_id", "date", "time", "boat_id", "status"],
        "audit_log": ["ts", "actor", "action", "entity", "entity_id", "diff_json"],
    }
    missing = {}
    for tab, cols in required.items():
        tab_missing = sheets.validate_required_columns(tab, cols)
        if tab_missing:
            missing[tab] = tab_missing
    if missing:
        raise ApiError(status_code=400, code="COLUMN_MISSING", message=str(missing))
    return {"ok": True}




@app.get("/ops/diagnostics")
def ops_diagnostics(
    _: dict = Depends(require_permission("write:admin")),
    sheets=Depends(get_sheets),
):
    ttl = int(os.environ.get("SHEETS_CACHE_TTL_SECONDS", "30"))
    return diagnostics_snapshot(
        sheets=sheets,
        app_version=app.version,
        cache_ttl_seconds=ttl,
    )

@app.get("/availability")
def availability(date: str, _: dict = Depends(require_permission("read:ops")), sheets=Depends(get_sheets)):
    return build_availability(sheets, date_iso=date)


@app.post("/bookings", response_model=BookingCreateResponse)
def bookings_create(
    request: BookingCreateRequest,
    session: dict = Depends(require_permission("write:ops")),
    sheets=Depends(get_sheets),
):
    return create_booking(
        sheets=sheets,
        request=request.model_dump(),
        actor=session["staff_user_id"],
    )


@app.post("/checkins")
def checkins_create(
    request: CheckinCreateRequest,
    session: dict = Depends(require_permission("write:ops")),
    sheets=Depends(get_sheets),
):
    return create_checkin(
        sheets=sheets,
        booking_id=request.booking_id,
        method=request.method,
        status=request.status,
        actor=session["staff_user_id"],
    )


@app.get("/pilot/today")
def pilot_today(
    boat_id: str,
    date: str,
    _: dict = Depends(require_permission("read:pilot")),
    sheets=Depends(get_sheets),
):
    return get_pilot_queue(sheets=sheets, date_iso=date, boat_id=boat_id)


@app.patch("/bookings/{booking_id}")
def bookings_patch(
    booking_id: str,
    request: BookingStatusPatchRequest,
    session: dict = Depends(current_session),
    sheets=Depends(get_sheets),
):
    if not has_permission(session["role"], "write:ops") and not has_permission(
        session["role"], "write:pilot"
    ):
        raise ApiError(status_code=403, code="FORBIDDEN", message="Forbidden by RBAC")
    return update_booking_status(
        sheets=sheets,
        booking_id=booking_id,
        new_status=request.status,
        actor=session["staff_user_id"],
        actor_role=session["role"],
    )


@app.get("/kpi/today")
def kpi_today(today: str, _: dict = Depends(require_permission("read:kpi")), sheets=Depends(get_sheets)):
    return kpi_view(sheets=sheets, period="today", today_iso=today)


@app.get("/kpi/week")
def kpi_week(today: str, _: dict = Depends(require_permission("read:kpi")), sheets=Depends(get_sheets)):
    return kpi_view(sheets=sheets, period="week", today_iso=today)


@app.get("/kpi/month")
def kpi_month(today: str, _: dict = Depends(require_permission("read:kpi")), sheets=Depends(get_sheets)):
    return kpi_view(sheets=sheets, period="month", today_iso=today)


@app.get("/kpi/drilldown")
def kpi_metric_drilldown(
    period: str,
    metric: str,
    today: str,
    _: dict = Depends(require_permission("read:kpi")),
    sheets=Depends(get_sheets),
):
    return kpi_drilldown(sheets=sheets, period=period, metric=metric, today_iso=today)
