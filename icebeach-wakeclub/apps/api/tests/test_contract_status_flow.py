"""Права на «следующий шаг» заезда — дашборд (lib/status-flow.ts) повторяет эту матрицу.

confirmed → «На месте» (PATCH /prep arrival_action=arrived): админ, оператор, пилот своего катера;
arrived → «Готово к старту» (PATCH /status ready): админ, оператор; пилоту нельзя;
ready → «На воде» и in_progress → «Завершено» — только таймер: админ и пилот; оператору нельзя.
Тренер статусы не меняет.
"""

from __future__ import annotations

from test_contract_equipment import _booking, _client, _demo_sheet, teardown_function  # noqa: F401


def test_operator_marks_arrival_in_one_tap_and_hands_off_to_pilot() -> None:
    sheet = _demo_sheet()
    operator = _client(sheet, "staff_001")
    assert _booking(operator, "bkg_demo_confirmed")["status"] == "confirmed"

    arrived = operator.patch("/bookings/bkg_demo_confirmed/prep", json={"arrival_action": "arrived"})
    assert arrived.status_code == 200, arrived.text
    assert arrived.json()["status"] == "arrived"

    ready = operator.patch("/bookings/bkg_demo_confirmed/status", json={"status": "ready"})
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "ready"

    # Старт сета — не оператору.
    start = operator.post("/bookings/bkg_demo_confirmed/timer-action", json={"action": "start"})
    assert start.status_code == 403


def test_pilot_can_arrive_and_run_timer_but_not_hand_off() -> None:
    sheet = _demo_sheet()
    pilot = _client(sheet, "staff_pilot")

    arrived = pilot.patch("/bookings/bkg_demo_confirmed/prep", json={"arrival_action": "arrived"})
    assert arrived.status_code == 200, arrived.text
    assert arrived.json()["status"] == "arrived"

    hand_off = pilot.patch("/bookings/bkg_demo_confirmed/status", json={"status": "ready"})
    assert hand_off.status_code == 403

    start = pilot.post("/bookings/bkg_demo_ready/timer-action", json={"action": "start"})
    assert start.status_code == 200, start.text
    assert start.json()["status"] == "in_progress"

    finish = pilot.post("/bookings/bkg_demo_ready/timer-action", json={"action": "stop"})
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "done"


def test_coach_cannot_change_status() -> None:
    sheet = _demo_sheet()
    coach = _client(sheet, "staff_coach")
    assert coach.patch("/bookings/bkg_demo_confirmed/prep", json={"arrival_action": "arrived"}).status_code == 403
    assert coach.patch("/bookings/bkg_demo_confirmed/status", json={"status": "arrived"}).status_code == 403
