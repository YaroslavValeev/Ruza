from datetime import date

from fastapi import APIRouter, Depends, Query

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
    sync_intake_leads(
        source_sheet,
        target_sheet,
        source_tab=settings.intake_tab_name,
        club_id=settings.public_club_id,
        actor="public-widget",
    )
    return PublicBookingRequestResponse(
        lead_id=lead_id_for_external(request_id),
        status="new",
        message="Заявка принята. Оператор свяжется для подтверждения записи.",
    )
