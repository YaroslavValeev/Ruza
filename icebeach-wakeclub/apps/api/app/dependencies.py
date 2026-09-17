from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, status

from packages.sheets import SheetWrapper

from .config import get_settings


@lru_cache(maxsize=1)
def get_sheet_wrapper() -> SheetWrapper:
    settings = get_settings()
    return SheetWrapper(
        spreadsheet_id=settings.spreadsheet_id,
        service_account_json_path=settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )


@lru_cache(maxsize=1)
def get_intake_sheet_wrapper() -> SheetWrapper:
    settings = get_settings()
    if not settings.intake_spreadsheet_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTAKE_SPREADSHEET_ID is not configured",
        )
    return SheetWrapper(
        spreadsheet_id=settings.intake_spreadsheet_id,
        service_account_json_path=settings.service_account_json_path,
        service_account_info=settings.service_account_info,
    )
