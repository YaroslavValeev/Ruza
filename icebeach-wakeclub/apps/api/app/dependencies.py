from __future__ import annotations

from functools import lru_cache

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
