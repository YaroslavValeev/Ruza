from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..agents_auth import verify_agents_secret
from ..config import Settings, get_settings
from ..dependencies import get_intake_sheet_wrapper, get_sheet_wrapper
from ..models import (
    AnalyticsSnapshotResponse,
    DailyBriefResponse,
    DailyBriefKpiSlice,
    DailyBriefUpcomingItem,
    MarkLateResponse,
    IntakeSyncResponse,
    PreflightSummaryResponse,
    ShiftSummary,
)
from ..services.analytics_snapshot import write_analytics_snapshot
from ..services.checkins import mark_late_checkins
from ..services.daily_brief import build_daily_brief
from ..services.preflight import run_preflight_check
from ..services.intake import sync_intake_leads


router = APIRouter(prefix="/internal/agents", tags=["internal-agents"])


@router.post("/intake-sync", response_model=IntakeSyncResponse, dependencies=[Depends(verify_agents_secret)])
def agents_intake_sync(
    source_sheet: SheetWrapper = Depends(get_intake_sheet_wrapper),
    target_sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> IntakeSyncResponse:
    result = sync_intake_leads(
        source_sheet,
        target_sheet,
        source_tab=settings.intake_tab_name,
        club_id=settings.public_club_id,
        actor=settings.agents_staff_user_id,
    )
    return IntakeSyncResponse(**result)


@router.get("/preflight", response_model=PreflightSummaryResponse, dependencies=[Depends(verify_agents_secret)])
def agents_preflight(
    date_value: date = Query(default_factory=date.today, alias="date"),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
) -> PreflightSummaryResponse:
    return PreflightSummaryResponse(**run_preflight_check(sheet, target_date=date_value.isoformat()))


@router.post("/mark-late", response_model=MarkLateResponse, dependencies=[Depends(verify_agents_secret)])
def agents_mark_late(
    date_value: date = Query(default_factory=date.today, alias="date"),
    minutes_before: int = Query(default=10, ge=1, le=120),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> MarkLateResponse:
    club_id = settings.public_club_id
    result = mark_late_checkins(
        sheet,
        club_id=club_id,
        target_date=date_value.isoformat(),
        actor_staff_user_id=settings.agents_staff_user_id,
        minutes_before=minutes_before,
    )
    return MarkLateResponse(**result)


@router.post("/snapshot", response_model=AnalyticsSnapshotResponse, dependencies=[Depends(verify_agents_secret)])
def agents_snapshot(
    date_value: date = Query(default_factory=date.today, alias="date"),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> AnalyticsSnapshotResponse:
    result = write_analytics_snapshot(sheet, club_id=settings.public_club_id, target_date=date_value.isoformat())
    return AnalyticsSnapshotResponse(**result)


@router.get("/daily-brief", response_model=DailyBriefResponse, dependencies=[Depends(verify_agents_secret)])
def agents_daily_brief(
    mode: str = Query(default="morning", pattern="^(morning|evening)$"),
    date_value: date = Query(default_factory=date.today, alias="date"),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> DailyBriefResponse:
    brief = build_daily_brief(
        sheet,
        club_id=settings.public_club_id,
        target_date=date_value.isoformat(),
        mode=mode,
    )
    summary = brief["summary"]
    kpi = brief["kpi"]
    assert isinstance(summary, dict)
    assert isinstance(kpi, dict)
    return DailyBriefResponse(
        mode=str(brief["mode"]),
        date=date_value,
        club_id=str(brief["club_id"]),
        title=str(brief["title"]),
        text=str(brief["text"]),
        summary=ShiftSummary(**summary),
        kpi=DailyBriefKpiSlice(
            sessions_count=int(kpi.get("sessions_count", 0)),
            utilization_pct=float(kpi.get("utilization_pct", 0)),
            revenue_estimate=int(kpi.get("revenue_estimate", 0)),
        ),
        upcoming=[DailyBriefUpcomingItem(**item) for item in brief.get("upcoming", [])],  # type: ignore[arg-type]
    )
