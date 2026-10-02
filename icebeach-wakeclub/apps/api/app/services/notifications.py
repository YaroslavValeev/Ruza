from __future__ import annotations

from datetime import datetime, timezone

import httpx

from packages.sheets import SheetWrapper

from ..config import Settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _send_telegram_message(*, bot_token: str, chat_id: str, text: str, timeout_seconds: float) -> None:
    response = httpx.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=timeout_seconds,
    )
    response.raise_for_status()


def _record_notification(
    sheet: SheetWrapper,
    *,
    actor: str,
    booking_id: str,
    action: str,
    channel: str,
    recipient: str,
    title: str,
    message: str,
) -> None:
    sheet.write_audit(
        action=action,
        entity="booking_notification",
        entity_id=booking_id,
        diff_json={
            "channel": channel,
            "recipient": recipient,
            "title": title,
            "message": message,
            "recorded_at": _now_iso(),
        },
        actor=actor,
    )


def send_admin_notice(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    booking_id: str,
    title: str,
    message: str,
    actor: str,
) -> str:
    channel = "manual"
    if settings.telegram_bot_token and settings.telegram_owner_chat_id:
        try:
            _send_telegram_message(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_owner_chat_id,
                text=f"{title}\n\n{message}",
                timeout_seconds=settings.otp_delivery_timeout_seconds,
            )
            channel = "telegram_owner"
        except Exception:
            channel = "manual"
    _record_notification(
        sheet,
        actor=actor,
        booking_id=booking_id,
        action="notify_admin",
        channel=channel,
        recipient="admin",
        title=title,
        message=message,
    )
    return channel


def send_client_notice(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    booking_id: str,
    client_row: dict[str, str],
    title: str,
    message: str,
    actor: str,
) -> str:
    telegram_id = str(client_row.get("telegram_id", "")).strip()
    channel = "manual"
    if settings.telegram_bot_token and telegram_id:
        try:
            _send_telegram_message(
                bot_token=settings.telegram_bot_token,
                chat_id=telegram_id,
                text=f"{title}\n\n{message}",
                timeout_seconds=settings.otp_delivery_timeout_seconds,
            )
            channel = "telegram_client"
        except Exception:
            channel = "manual"
    _record_notification(
        sheet,
        actor=actor,
        booking_id=booking_id,
        action="notify_client",
        channel=channel,
        recipient=client_row.get("phone", "") or client_row.get("client_id", ""),
        title=title,
        message=message,
    )
    return channel
