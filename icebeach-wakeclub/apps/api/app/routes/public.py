from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.sheets import SheetWrapper

from ..config import Settings, get_settings
from ..dependencies import get_intake_sheet_wrapper, get_sheet_wrapper
from ..models import AvailabilityItem, PublicBookingRequest, PublicBookingRequestResponse
from ..services.availability import get_availability_for_date
from ..services.intake import create_canonical_booking_request, lead_id_for_external, sync_intake_leads


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/availability", response_model=list[AvailabilityItem])
def public_availability(
    date_value: date = Query(..., alias="date"),
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> list[AvailabilityItem]:
    return get_availability_for_date(sheet, date_value.isoformat(), settings.public_club_id)


@router.post("/booking-request", response_model=PublicBookingRequestResponse)
def public_booking_request(
    payload: PublicBookingRequest,
    source_sheet: SheetWrapper = Depends(get_intake_sheet_wrapper),
    target_sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> PublicBookingRequestResponse:
    request_id = create_canonical_booking_request(
        source_sheet,
        payload,
        source_tab=settings.intake_tab_name,
    )
    lead_id = lead_id_for_external(request_id)
    sync_result = sync_intake_leads(
        source_sheet,
        target_sheet,
        source_tab=settings.intake_tab_name,
        club_id=settings.public_club_id,
        actor="public-widget",
    )
    created_lead = next(
        (
            row
            for row in target_sheet.find("leads", {"lead_id": lead_id})
            if row.get("club_id") == settings.public_club_id and row.get("external_record_id") == request_id
        ),
        None,
    )
    if created_lead is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "operational_lead_missing",
                "message": "Не удалось принять заявку: операционный лид не создан.",
                "lead_id": lead_id,
                "sync_errors": list(sync_result.get("errors", [])),
            },
        )
    return PublicBookingRequestResponse(
        lead_id=lead_id,
        status="new",
        message="Заявка принята. Оператор свяжется для подтверждения записи.",
    )
