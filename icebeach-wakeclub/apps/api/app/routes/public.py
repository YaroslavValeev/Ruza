from datetime import date

from fastapi import APIRouter, Depends, Query

from packages.sheets import SheetWrapper

from ..config import Settings, get_settings
from ..dependencies import get_sheet_wrapper
from ..models import AvailabilityItem, LeadCreateRequest, PublicBookingRequest, PublicBookingRequestResponse
from ..services.availability import get_availability_for_date
from ..services.leads import create_lead


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
    sheet: SheetWrapper = Depends(get_sheet_wrapper),
    settings: Settings = Depends(get_settings),
) -> PublicBookingRequestResponse:
    notes = (
        f"Запрос слота: {payload.date.isoformat()} {payload.time}, "
        f"тип {payload.ride_type}. {payload.notes}".strip()
    )
    lead = create_lead(
        sheet,
        LeadCreateRequest(
            full_name=payload.full_name,
            phone=payload.phone,
            source="public_widget",
            utm_source="public_book",
            notes=notes,
        ),
        actor_staff_user_id="public-widget",
        club_id=settings.public_club_id,
    )
    return PublicBookingRequestResponse(
        lead_id=lead["lead_id"],
        status="new",
        message="Заявка принята. Оператор свяжется для подтверждения записи.",
    )
