# Week 2 Execution Plan — Availability + Create Booking

## Шаг 1. Зафиксировать Week 1 verification (A–F)

- A) `/health` отвечает 200 (локально через API тест).
- B) Login role mapping из `staff_users` (на боевой таблице вручную: admin/pilot).
- C) RBAC на backend (operator/pilot/marketing_read ограничения).
- D) `POST /ops/audit-test` пишет в `audit_log` и `diff_json`.
- E) `schema-check` возвращает `COLUMN_MISSING` / `TAB_MISSING`.
- F) pre-push hook блокирует push, кроме `ALLOW_GIT_PUSH=1`.

## Шаг 2. API: `/availability`

1. Валидировать дату (`YYYY-MM-DD`).
2. Прочитать `schedule` по `weekday` и `is_active=true`.
3. Применить `slot_overrides` для даты.
4. Вычесть активные `bookings` (`status != cancelled`).
5. Вернуть `date,time,boat_id,capacity,booked_count,remaining,status`.

## Шаг 3. API: `POST /bookings`

1. Нормализовать `time` в `HH:MM`.
2. Вычислить детерминированный `booking_id`.
3. Проверить идемпотентность по `booking_id`.
4. Повторно проверить capacity через availability.
5. Сделать append в `bookings`.
6. Записать `write_audit(action=create, entity=booking)`.

## Шаг 4. Ошибки и контракты

- `SLOT_FULL`
- `INVALID_DATE`
- `TAB_MISSING`
- `COLUMN_MISSING`
- `UNAUTHORIZED`
- `FORBIDDEN`

## Шаг 5. Тесты Week 2

- Availability: пустой день, remaining корректный.
- Create booking: 1) create 1 раз, 2) idempotent replay, 3) slot full -> отказ.
- Security: token содержит `iat`/`exp`, RBAC rules проходят.

## Шаг 6. Operator UI (минимум)

- Date picker.
- Список слотов с `remaining`.
- Форма создания брони.

## Шаг 7. Gate-check перед merge

- Gate A/B/C подтверждены автоматически тестами + ручной smoke в Sheets.
- Gate D/E проверены контрактными тестами + schema-check endpoint.

UI proof attached: screenshots/week2_operator_availability.svg, screenshots/week2_operator_create_success.svg
