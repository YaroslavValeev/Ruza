"""OTP delivery adapters. Secrets stay in env; never commit tokens."""

from __future__ import annotations

import os

import httpx


def deliver_login_code(*, code: str, telegram_id: str = "") -> str:
    """Send login code if a provider is configured. Always safe to call.

    Returns the delivery channel actually used: ``telegram`` or ``manual``.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = (telegram_id or "").strip()
    if not token or not chat_id:
        return "manual"
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"Код входа Ice Beach: {code}"},
            timeout=8.0,
        )
        if response.status_code >= 400:
            return "manual"
        return "telegram"
    except Exception:
        return "manual"
