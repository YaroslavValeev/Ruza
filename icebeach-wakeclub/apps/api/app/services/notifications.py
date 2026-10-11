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
    payload = response.json()
    result = payload.get("result") if isinstance(payload, dict) else None
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("ok") is not True
        or type(message_id) is not int
        or message_id <= 0
    ):
        raise ValueError("Telegram did not confirm message delivery")


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
    delivery_status: str,
    notification_key: str | None,
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
            "delivery_status": delivery_status,
            "pending": delivery_status != "delivered",
            "manual_required": delivery_status == "manual_required",
            "retryable": delivery_status != "delivered",
            "notification_key": notification_key,
        },
        actor=actor,
        strict=True,
    )


def send_admin_notice(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    booking_id: str,
    title: str,
    message: str,
    actor: str,
    notification_key: str | None = None,
) -> str:
    channel = "manual"
    delivery_status = "manual_required"
    if settings.telegram_bot_token and settings.telegram_owner_chat_id:
        channel = "telegram_owner"
        try:
            _send_telegram_message(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_owner_chat_id,
                text=f"{title}\n\n{message}",
                timeout_seconds=settings.otp_delivery_timeout_seconds,
            )
            delivery_status = "delivered"
        except Exception:
            # Provider errors can contain bot tokens, URLs and recipient data.
            delivery_status = "failed"
    _record_notification(
        sheet,
        actor=actor,
        booking_id=booking_id,
        action="notify_admin",
        channel=channel,
        recipient="admin",
        title=title,
        message=message,
        delivery_status=delivery_status,
        notification_key=notification_key,
    )
    return channel if delivery_status == "delivered" else delivery_status


def send_client_notice(
    sheet: SheetWrapper,
    settings: Settings,
    *,
    booking_id: str,
    client_row: dict[str, str],
    title: str,
    message: str,
    actor: str,
    notification_key: str | None = None,
) -> str:
    telegram_id = str(client_row.get("telegram_id") or "").strip()
    channel = "manual"
    delivery_status = "manual_required"
    if settings.telegram_bot_token and telegram_id:
        channel = "telegram_client"
        try:
            _send_telegram_message(
                bot_token=settings.telegram_bot_token,
                chat_id=telegram_id,
                text=f"{title}\n\n{message}",
                timeout_seconds=settings.otp_delivery_timeout_seconds,
            )
            delivery_status = "delivered"
        except Exception:
            delivery_status = "failed"
    _record_notification(
        sheet,
        actor=actor,
        booking_id=booking_id,
        action="notify_client",
        channel=channel,
        recipient=client_row.get("phone", "") or client_row.get("client_id", ""),
        title=title,
        message=message,
        delivery_status=delivery_status,
        notification_key=notification_key,
    )
    return channel if delivery_status == "delivered" else delivery_status
