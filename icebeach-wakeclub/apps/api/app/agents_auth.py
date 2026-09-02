from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


def verify_agents_secret(
    x_agents_secret: str | None = Header(default=None, alias="X-Agents-Secret"),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.agents_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AGENTS_SECRET is not configured",
        )
    if not x_agents_secret or x_agents_secret != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agents secret")
