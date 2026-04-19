# Week 3 Execution Plan — Check-in + Pilot Queue + Session Status

## Goal

Сделать “премиум-эффект” смены: operator фиксирует готовность, pilot ведёт очередь и статусы в одном экране без хаоса.

## Deliverables

### 1) Backend: Check-ins

- `POST /checkins`
- input: `booking_id`, `method=phone|manual`, `status=arrived|ready|late`
- side effects:
  - append в `checkins`
  - update `bookings.status -> checked_in` для `arrived/ready`
  - `write_audit` для checkin и booking

### 2) Backend: Pilot queue

- `GET /pilot/today?boat_id=...&date=YYYY-MM-DD`
- output: `time`, `client(masked)`, `status`, `ready_state`, `notes`
- сортировка по времени

### 3) Backend: Status transitions

- `PATCH /bookings/{booking_id}`
- role transitions:
  - `pilot`: `checked_in -> in_progress -> done/no_show`
  - `operator`: `confirmed -> cancelled/no_show`, `confirmed -> checked_in`
  - `admin`: любые валидные переходы
- audit обязательно

### 4) UI: Operator controls

- Кнопки `Arrived / Ready / Late`
- Отображение `booking status` и `ready_state`
- One-click update

### 5) UI: Pilot screen

- date + boat filter (`today` default)
- очередь
- кнопки `Start / Done`

## Week 3 Gate-check

1. checkin создаёт запись + обновляет booking + audit
2. pilot/today возвращает правильный ready state
3. role-based transition rules enforced
4. сценарий на руках: checkin -> pilot start -> done -> audit trail

## Cutline

- KPI expansion: Week 4
- Marketing/forecast: Week 4+
- Voice prod / face recognition: позже

E2E flow PASS:
1) create booking -> bookings row,
2) arrived check-in -> checkins row + booking checked_in,
3) pilot queue shows ready_state,
4) start -> in_progress,
5) done -> done,
6) audit_log chain present.
