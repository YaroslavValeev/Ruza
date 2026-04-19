"""Dependency provider for SheetWrapper."""

from __future__ import annotations

from packages.sheets import SheetWrapper, SheetsConfig


def get_sheets() -> SheetWrapper:
    return SheetWrapper(SheetsConfig.from_env())
