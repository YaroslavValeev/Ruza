"""OTP delivery adapters. Secrets stay in settings; codes are never logged."""

from __future__ import annotations

import httpx

from ..config import Settings


class OtpDeliveryError(RuntimeError):
    """Raised when no configured OTP channel could deliver the code."""


def _deliver_webhook(*, code: str, phone: str, settings: Settings) -> None:
    response = httpx.post(
        settings.otp_delivery_webhook_url,
        headers={"Authorization": f"Bearer {settings.otp_delivery_webhook_token}"},
        json={"phone": phone, "code": code, "purpose": "staff_login"},
        timeout=settings.otp_delivery_timeout_seconds,
    )
    response.raise_for_status()


def _deliver_telegram(*, code: str, telegram_id: str, settings: Settings) -> None:
    response = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        json={"chat_id": telegram_id, "text": f"Код входа Ice Beach: {code}"},
        timeout=settings.otp_delivery_timeout_seconds,
    )
    response.raise_for_status()


def deliver_login_code(
    *,
    code: str,
    phone: str,
    settings: Settings,
    telegram_id: str = "",
) -> str:
    """Deliver a staff OTP and return the channel that accepted it.

    The phone webhook is canonical. Telegram is a supported fallback for staff
    records that contain ``telegram_id``. Manual delivery is local/test only.
    """
    if settings.otp_delivery_webhook_url:
        try:
            _deliver_webhook(code=code, phone=phone, settings=settings)
            return "phone_webhook"
        except Exception as exc:
            raise OtpDeliveryError("Phone OTP provider rejected the request") from exc

    chat_id = telegram_id.strip()
    if settings.telegram_bot_token and chat_id:
        try:
            _deliver_telegram(code=code, telegram_id=chat_id, settings=settings)
            return "telegram"
        except Exception as exc:
            if not settings.allow_manual_otp_delivery:
                raise OtpDeliveryError("Telegram OTP provider rejected the request") from exc

    if settings.allow_manual_otp_delivery:
        return "manual"

    raise OtpDeliveryError("No OTP delivery provider is configured")
