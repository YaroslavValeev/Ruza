from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Barrier
from time import sleep
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import httpx
import pytest

from apps.api.app.services import notifications
from apps.api.app.services.bookings import RIDE_RUNTIME_DEFAULTS
from apps.api.app.services.shift_timer import (
    process_shift_reminders,
    run_timer_action,
    update_booking_prep,
)

from conftest import MockSheetWrapper, make_test_settings


CLUB_ID = "ice_beach_ruza"
CLUB_TZ = ZoneInfo("Europe/Moscow")
T15 = datetime(2026, 6, 1, 9, 45, tzinfo=CLUB_TZ)
T5 = datetime(2026, 6, 1, 9, 55, tzinfo=CLUB_TZ)


def test_overdue_late_mark_does_not_send_future_start_reminder(telegram_post: Mock) -> None:
    sheet = _sheet()
    update_booking_prep(
        sheet, _settings(), booking_id="notice-booking", arrival_action="late",
        warmup_state=None, actor_staff_user_id="test-actor", club_id=CLUB_ID,
        now=datetime(2026, 6, 1, 10, 1, tzinfo=CLUB_TZ),
    )
    assert _row(sheet)["status"] == "late"
    assert not _row(sheet).get("client_notice_15_sent_at")
    telegram_post.assert_not_called()


def test_concurrent_reminder_runs_send_one_confirmed_notice(telegram_post: Mock) -> None:
    sheet = _sheet()
    barrier = Barrier(2)

    def delayed_response(*args, **kwargs):
        sleep(0.01)
        return _response()

    telegram_post.side_effect = delayed_response

    def run():
        barrier.wait(timeout=5)
        return process_shift_reminders(sheet, _settings(), club_id=CLUB_ID, actor_staff_user_id="test-actor", now=T15)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert sum(result["admin_notices_sent"] for result in results) == 1
    assert telegram_post.call_count == 1


@pytest.fixture(autouse=True)
def telegram_post(monkeypatch: pytest.MonkeyPatch) -> Mock:
    # Never let these contracts contact a provider, even if a test forgets a mock.
    post = Mock(side_effect=AssertionError("Unmocked Telegram request"))
    monkeypatch.setattr(notifications.httpx, "post", post)
    return post


def _response(payload: object = None, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=(
            payload
            if payload is not None
            else {"ok": True, "result": {"message_id": 42}}
        ),
        request=httpx.Request("POST", "https://provider.invalid/send"),
    )


def _settings():
    return replace(
        make_test_settings(),
        telegram_bot_token="fake-bot",
        telegram_owner_chat_id="fake-owner",
    )


def _sheet(
    *, status: str = "confirmed", date: str = "2026-06-01", time: str = "10:00"
) -> MockSheetWrapper:
    sheet = MockSheetWrapper()
    for client in sheet.tabs["clients"]:
        client["telegram_id"] = f"fake-{client['client_id']}"
    sheet.tabs["bookings"].append(
        {
            **RIDE_RUNTIME_DEFAULTS,
            "booking_id": "notice-booking",
            "club_id": CLUB_ID,
            "client_id": "client_1",
            "date": date,
            "time": time,
            "boat_id": "boat_1",
            "status": status,
            "sets_count": "1",
            "total_price": "12000",
        }
    )
    return sheet


def _row(sheet: MockSheetWrapper) -> dict[str, str]:
    return sheet.find("bookings", {"booking_id": "notice-booking"})[0]


def _audits(sheet: MockSheetWrapper) -> list[dict]:
    return [
        ast.literal_eval(row["diff_json"])
        for row in sheet.read_tab("audit_log")
        if row["entity"] == "booking_notification"
    ]


def _send(sheet: MockSheetWrapper, settings, recipient: str) -> str:
    kwargs = dict(
        booking_id="notice-booking",
        title="Test title",
        message="Test message",
        actor="test-actor",
    )
    if recipient == "admin":
        return notifications.send_admin_notice(sheet, settings, **kwargs)
    return notifications.send_client_notice(
        sheet, settings, client_row=sheet.tabs["clients"][0], **kwargs
    )


@pytest.mark.parametrize("recipient", ["admin", "client"])
@pytest.mark.parametrize("unavailable", ["token", "recipient"])
def test_unavailable_delivery_requires_manual_action(
    recipient: str, unavailable: str, telegram_post: Mock
) -> None:
    sheet = _sheet()
    settings = _settings()
    if unavailable == "token":
        settings = replace(settings, telegram_bot_token=None)
    elif recipient == "admin":
        settings = replace(settings, telegram_owner_chat_id=None)
    else:
        sheet.tabs["clients"][0]["telegram_id"] = ""
    assert _send(sheet, settings, recipient) == "manual_required"
    telegram_post.assert_not_called()
    audit = _audits(sheet)[0]
    assert audit["delivery_status"] == "manual_required"
    assert audit["channel"] == "manual"
    assert audit["pending"] and audit["manual_required"] and audit["retryable"]


@pytest.mark.parametrize("telegram_id", [None, "   "])
def test_empty_client_recipient_is_not_sent(telegram_id, telegram_post: Mock) -> None:
    sheet = _sheet()
    sheet.tabs["clients"][0]["telegram_id"] = telegram_id
    assert _send(sheet, _settings(), "client") == "manual_required"
    telegram_post.assert_not_called()


@pytest.mark.parametrize(
    "recipient,channel", [("admin", "telegram_owner"), ("client", "telegram_client")]
)
def test_confirmed_delivery_preserves_success_channel(
    recipient: str, channel: str, telegram_post: Mock
) -> None:
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    sheet = _sheet()
    assert _send(sheet, _settings(), recipient) == channel
    audit = _audits(sheet)[0]
    assert audit["delivery_status"] == "delivered"
    assert audit["channel"] == channel
    assert (
        not audit["pending"] and not audit["manual_required"] and not audit["retryable"]
    )
    assert (
        telegram_post.call_args.kwargs["timeout"]
        == _settings().otp_delivery_timeout_seconds
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"ok": False, "description": "sensitive-provider-detail"},
        {"ok": "true", "result": {"message_id": 42}},
        {"ok": 1, "result": {"message_id": 42}},
        {"ok": True},
        {"ok": True, "result": []},
        {"ok": True, "result": {}},
        {"ok": True, "result": {"message_id": True}},
        {"ok": True, "result": {"message_id": 0}},
        {"ok": True, "result": {"message_id": "42"}},
        ["unexpected"],
    ],
)
@pytest.mark.parametrize("recipient", ["admin", "client"])
def test_unconfirmed_telegram_result_is_failed(
    payload: object, recipient: str, telegram_post: Mock, caplog
) -> None:
    telegram_post.side_effect = None
    telegram_post.return_value = _response(payload)
    sheet = _sheet()
    assert _send(sheet, _settings(), recipient) == "failed"
    audit = _audits(sheet)[0]
    assert audit["delivery_status"] == "failed"
    assert audit["pending"] and audit["retryable"] and not audit["manual_required"]
    assert "sensitive-provider-detail" not in str(sheet.tabs["audit_log"]) + caplog.text


@pytest.mark.parametrize("failure", ["http", "timeout", "json"])
@pytest.mark.parametrize("recipient", ["admin", "client"])
def test_provider_failure_is_retryable_without_sensitive_logging(
    failure: str, recipient: str, telegram_post: Mock, caplog
) -> None:
    sensitive = "fake-bot sensitive-provider-detail"
    if failure == "timeout":
        telegram_post.side_effect = httpx.ReadTimeout(sensitive)
    else:
        telegram_post.side_effect = None
        telegram_post.return_value = (
            _response({"description": sensitive}, status_code=503)
            if failure == "http"
            else httpx.Response(
                200,
                text=sensitive,
                request=httpx.Request("POST", "https://provider.invalid"),
            )
        )
    sheet = _sheet()
    assert _send(sheet, _settings(), recipient) == "failed"
    assert _audits(sheet)[0]["delivery_status"] == "failed"
    evidence = str(sheet.tabs["audit_log"]) + caplog.text
    assert "fake-bot" not in evidence and "sensitive-provider-detail" not in evidence
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _send(sheet, _settings(), recipient).startswith("telegram_")
    assert [audit["delivery_status"] for audit in _audits(sheet)] == [
        "failed",
        "delivered",
    ]


def _process(sheet: MockSheetWrapper, settings, now: datetime = T15) -> dict[str, int]:
    return process_shift_reminders(
        sheet, settings, club_id=CLUB_ID, actor_staff_user_id="test-actor", now=now
    )


@pytest.mark.parametrize("first_outcome", ["manual_required", "failed"])
def test_admin_reminder_marks_and_counts_only_success(
    first_outcome: str, telegram_post: Mock
) -> None:
    sheet = _sheet()
    settings = (
        make_test_settings() if first_outcome == "manual_required" else _settings()
    )
    telegram_post.side_effect = httpx.ReadTimeout("fake provider failure")
    for _ in range(2):
        assert _process(sheet, settings) == {
            "admin_notices_sent": 0,
            "client_notices_sent": 0,
        }
        assert not _row(sheet)["admin_notice_15_sent_at"]
    assert [a["delivery_status"] for a in _audits(sheet)] == [
        first_outcome,
        first_outcome,
    ]
    assert all(
        a["notification_key"] == "admin_notice_15_sent_at" for a in _audits(sheet)
    )
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _process(sheet, _settings()) == {
        "admin_notices_sent": 1,
        "client_notices_sent": 0,
    }
    assert (
        _row(sheet)["admin_notice_15_sent_at"]
        == T15.astimezone(timezone.utc).isoformat()
    )
    calls = telegram_post.call_count
    assert _process(sheet, _settings()) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 0,
    }
    assert telegram_post.call_count == calls


@pytest.mark.parametrize("first_outcome", ["manual_required", "failed"])
def test_late_prep_notice_can_be_retried_by_scheduler(
    first_outcome: str, telegram_post: Mock
) -> None:
    sheet = _sheet()
    settings = (
        make_test_settings() if first_outcome == "manual_required" else _settings()
    )
    telegram_post.side_effect = httpx.ReadTimeout("fake provider failure")
    update_booking_prep(
        sheet,
        settings,
        booking_id="notice-booking",
        arrival_action="late",
        warmup_state=None,
        actor_staff_user_id="test-actor",
        club_id=CLUB_ID,
        now=T15,
    )
    assert not _row(sheet)["client_notice_15_sent_at"]
    assert _audits(sheet)[0]["delivery_status"] == first_outcome
    assert _process(sheet, settings) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 0,
    }
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _process(sheet, _settings()) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 1,
    }
    assert _row(sheet)["client_notice_15_sent_at"]
    calls = telegram_post.call_count
    assert _process(sheet, _settings()) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 0,
    }
    assert telegram_post.call_count == calls


@pytest.mark.parametrize("first_outcome", ["manual_required", "failed"])
def test_t5_notices_retry_without_false_counts(
    first_outcome: str, telegram_post: Mock
) -> None:
    sheet = _sheet(status="late")
    _row(sheet)["client_notice_15_sent_at"] = T15.isoformat()
    settings = (
        make_test_settings() if first_outcome == "manual_required" else _settings()
    )
    telegram_post.side_effect = httpx.ReadTimeout("fake provider failure")
    assert _process(sheet, settings, T5) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 0,
    }
    assert (
        not _row(sheet)["admin_notice_5_sent_at"]
        and not _row(sheet)["client_notice_5_sent_at"]
    )
    assert [a["delivery_status"] for a in _audits(sheet)] == [
        first_outcome,
        first_outcome,
    ]
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _process(sheet, _settings(), T5) == {
        "admin_notices_sent": 1,
        "client_notices_sent": 1,
    }
    assert (
        _row(sheet)["admin_notice_5_sent_at"] and _row(sheet)["client_notice_5_sent_at"]
    )
    calls = telegram_post.call_count
    assert _process(sheet, _settings(), T5) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 0,
    }
    assert telegram_post.call_count == calls


def test_t5_requires_delivered_t15_and_retries_both_in_order(
    telegram_post: Mock,
) -> None:
    sheet = _sheet(status="late")
    telegram_post.side_effect = [_response(), _response({"ok": False})]
    assert _process(sheet, _settings(), T5) == {
        "admin_notices_sent": 1,
        "client_notices_sent": 0,
    }
    assert [a["notification_key"] for a in _audits(sheet)] == [
        "admin_notice_5_sent_at",
        "client_notice_15_sent_at",
    ]
    assert (
        not _row(sheet)["client_notice_15_sent_at"]
        and not _row(sheet)["client_notice_5_sent_at"]
    )
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _process(sheet, _settings(), T5) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 2,
    }
    assert (
        _row(sheet)["client_notice_15_sent_at"]
        and _row(sheet)["client_notice_5_sent_at"]
    )


@pytest.mark.parametrize("outcome", ["manual_required", "failed", "delivered"])
def test_notify_next_client_retries_failure_but_never_resends_success(
    outcome: str, telegram_post: Mock
) -> None:
    sheet = _sheet(status="in_progress")
    next_row = {
        **_row(sheet),
        "booking_id": "next-booking",
        "client_id": "client_2",
        "time": "11:00",
        "status": "confirmed",
    }
    sheet.tabs["bookings"].append(next_row)
    settings = make_test_settings() if outcome == "manual_required" else _settings()
    telegram_post.side_effect = (
        None if outcome == "delivered" else httpx.ReadTimeout("fake provider failure")
    )
    telegram_post.return_value = _response()

    def notify(settings):
        return run_timer_action(
            sheet,
            settings,
            booking_id="notice-booking",
            action="notify_next_client",
            actor_staff_user_id="test-actor",
            club_id=CLUB_ID,
            now=T15,
        )

    notify(settings)
    notify(settings)
    if outcome == "delivered":
        assert telegram_post.call_count == 1
        assert len(_audits(sheet)) == 1
    else:
        assert not _row(sheet)["next_client_notified_at"]
        assert [a["delivery_status"] for a in _audits(sheet)] == [outcome, outcome]
        telegram_post.side_effect = None
        notify(_settings())
    assert _row(sheet)["next_client_notified_at"]
    calls = telegram_post.call_count
    notify(_settings())
    assert telegram_post.call_count == calls
    assert all(
        row["entity_id"] == "next-booking"
        for row in sheet.tabs["audit_log"]
        if row["entity"] == "booking_notification"
    )


@pytest.mark.parametrize(
    "club_zone,date,time,now",
    [
        (
            "Europe/Moscow",
            "2026-06-01",
            "10:00",
            datetime(2026, 6, 1, 6, 45, tzinfo=timezone.utc),
        ),
        (
            "Asia/Vladivostok",
            "2026-06-01",
            "00:20",
            datetime(2026, 5, 31, 14, 5, tzinfo=timezone.utc),
        ),
    ],
)
def test_reminders_use_club_timezone_and_local_date(
    club_zone: str, date: str, time: str, now: datetime, telegram_post: Mock
) -> None:
    sheet = _sheet(date=date, time=time)
    sheet.tabs["clubs"][0]["timezone"] = club_zone
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _process(sheet, _settings(), now) == {
        "admin_notices_sent": 1,
        "client_notices_sent": 0,
    }
    assert _row(sheet)["admin_notice_15_sent_at"] == now.isoformat()


@pytest.mark.parametrize("minutes_before", [16, -1])
def test_reminders_do_not_send_outside_window(
    minutes_before: int, telegram_post: Mock
) -> None:
    sheet = _sheet()
    now = datetime(2026, 6, 1, 10, tzinfo=CLUB_TZ) - timedelta(minutes=minutes_before)
    assert _process(sheet, _settings(), now) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 0,
    }
    telegram_post.assert_not_called()
    assert not _audits(sheet)


@pytest.mark.parametrize("first_outcome", ["manual_required", "failed"])
def test_repeat_late_prep_retries_until_success(
    first_outcome: str, telegram_post: Mock
) -> None:
    sheet = _sheet()
    settings = (
        make_test_settings() if first_outcome == "manual_required" else _settings()
    )
    telegram_post.side_effect = httpx.ReadTimeout("fake provider failure")

    def mark_late(settings):
        return update_booking_prep(
            sheet,
            settings,
            booking_id="notice-booking",
            arrival_action="late",
            warmup_state=None,
            actor_staff_user_id="test-actor",
            club_id=CLUB_ID,
            now=T15,
        )

    mark_late(settings)
    mark_late(settings)
    assert not _row(sheet)["client_notice_15_sent_at"]
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    mark_late(_settings())
    assert _row(sheet)["client_notice_15_sent_at"]
    calls = telegram_post.call_count
    mark_late(_settings())
    assert telegram_post.call_count == calls
    assert [a["delivery_status"] for a in _audits(sheet)] == [
        first_outcome,
        first_outcome,
        "delivered",
    ]


def test_successful_admin_notice_is_not_repeated_when_client_delivery_fails(
    telegram_post: Mock,
) -> None:
    sheet = _sheet(status="late")
    _row(sheet)["client_notice_15_sent_at"] = T15.isoformat()
    telegram_post.side_effect = [_response(), _response({"ok": False})]
    assert _process(sheet, _settings(), T5) == {
        "admin_notices_sent": 1,
        "client_notices_sent": 0,
    }
    assert (
        _row(sheet)["admin_notice_5_sent_at"]
        and not _row(sheet)["client_notice_5_sent_at"]
    )
    telegram_post.side_effect = None
    telegram_post.return_value = _response()
    assert _process(sheet, _settings(), T5) == {
        "admin_notices_sent": 0,
        "client_notices_sent": 1,
    }
    assert telegram_post.call_count == 3
    assert telegram_post.call_args.kwargs["json"]["chat_id"] == "fake-client_1"


@pytest.mark.parametrize("outcome", ["manual_required", "failed", "delivered"])
def test_audit_storage_failure_is_not_silently_ignored(
    outcome: str, telegram_post: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _sheet()
    settings = make_test_settings() if outcome == "manual_required" else _settings()
    telegram_post.side_effect = (
        httpx.ReadTimeout("fake provider failure") if outcome == "failed" else None
    )
    telegram_post.return_value = _response()
    audit_writer = Mock(side_effect=RuntimeError("Audit storage unavailable"))
    monkeypatch.setattr(sheet, "write_audit", audit_writer)
    with pytest.raises(RuntimeError, match="Audit storage unavailable"):
        _send(sheet, settings, "client")
    assert audit_writer.call_args.kwargs["strict"] is True
    assert audit_writer.call_args.kwargs["diff_json"]["delivery_status"] == outcome


@pytest.mark.parametrize("operation", ["notify_next_client", "late_prep"])
def test_direct_concurrent_client_notices_send_once(
    operation: str, telegram_post: Mock
) -> None:
    sheet = _sheet(
        status="in_progress" if operation == "notify_next_client" else "confirmed"
    )
    sheet.tabs["bookings"].append(
        {
            **_row(sheet),
            "booking_id": "next-booking",
            "client_id": "client_2",
            "time": "11:00",
            "status": "confirmed",
        }
    )

    def slow_delivery(*args, **kwargs):
        sleep(0.01)
        return _response()

    telegram_post.side_effect = slow_delivery
    barrier = Barrier(2)

    def notify():
        barrier.wait(timeout=5)
        if operation == "late_prep":
            return update_booking_prep(
                sheet,
                _settings(),
                booking_id="notice-booking",
                arrival_action="late",
                warmup_state=None,
                actor_staff_user_id="test-actor",
                club_id=CLUB_ID,
                now=T15,
            )
        return run_timer_action(
            sheet,
            _settings(),
            booking_id="notice-booking",
            action="notify_next_client",
            actor_staff_user_id="test-actor",
            club_id=CLUB_ID,
            now=T15,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(notify) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert all(item["booking_id"] == "notice-booking" for item in results)
    assert telegram_post.call_count == 1
    marker = (
        "next_client_notified_at"
        if operation == "notify_next_client"
        else "client_notice_15_sent_at"
    )
    assert _row(sheet)[marker]
    assert len(_audits(sheet)) == 1
