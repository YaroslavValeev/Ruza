import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from googleapiclient.errors import HttpError

from .config import get_settings
from .routes.analytics import router as analytics_router
from .routes.approvals import router as approvals_router
from .routes.auth import router as auth_router
from .routes.availability import router as availability_router
from .routes.bookings import router as bookings_router
from .routes.checkins import router as checkins_router
from .routes.clients import router as clients_router
from .routes.health import router as health_router
from .routes.internal_agents import router as internal_agents_router
from .routes.kpi import router as kpi_router
from .routes.leads import router as leads_router
from .routes.marketing import router as marketing_router
from .routes.pilot import router as pilot_router
from .routes.preflight import router as preflight_router
from .routes.public import router as public_router
from .routes.shift import router as shift_router
from .routes.smoke import router as smoke_router
from .routes.utm import router as utm_router


app = FastAPI(title="Ice Beach Wake Club API", version="0.2.0")
settings = get_settings()


def _extract_tab_name(exc: HttpError) -> str | None:
    uri = getattr(exc, "uri", "") or ""
    match = re.search(r"/values/([^%]+)%21", uri)
    if match:
        return match.group(1)

    text = str(exc)
    match = re.search(r"range: ([^!\s]+)!", text)
    if match:
        return match.group(1)

    return None


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(HttpError)
async def google_http_error_handler(_request: Request, exc: HttpError):
    tab = _extract_tab_name(exc)
    status_code = getattr(getattr(exc, "resp", None), "status", None)

    if status_code == 400 and tab and "Unable to parse range" in str(exc):
        return JSONResponse(
            status_code=400,
            content={"detail": f"Missing or misnamed sheet tab: {tab}"},
        )

    return JSONResponse(
        status_code=502,
        content={
            "detail": "Google Sheets error",
            "google_status": status_code,
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(availability_router)
app.include_router(bookings_router)
app.include_router(clients_router)
app.include_router(pilot_router)
app.include_router(kpi_router)
app.include_router(preflight_router)
app.include_router(smoke_router)
app.include_router(checkins_router)
app.include_router(analytics_router)
app.include_router(leads_router)
app.include_router(marketing_router)
app.include_router(utm_router)
app.include_router(shift_router)
app.include_router(internal_agents_router)
app.include_router(public_router)
app.include_router(approvals_router)
