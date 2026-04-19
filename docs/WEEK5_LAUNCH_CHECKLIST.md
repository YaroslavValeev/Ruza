# Week 5 Launch Checklist (MVP READY)

## Быстрый прогон перед сменой

1. Запустить API и проверить `GET /health` (ожидание: 200).  
   Если упало: проверить `.env` и доступ к `GOOGLE_SERVICE_ACCOUNT_JSON`.
2. Запустить dashboard (`npm run dev`) и открыть `/operator`, `/pilot`, `/kpi`.
3. Проверить `GET /ops/diagnostics` под admin (ожидание: `status=ok|warn` с причинами).

## Smoke по ролям

### Admin
4. Login admin работает, доступ к `/ops/diagnostics` есть.
5. Видит KPI cards + drilldown.

### Operator
6. `availability` отображает слоты и `remaining`.
7. `create booking` создаёт запись в `bookings`.
8. Повтор create тем же payload -> нет дубля (`idempotent_replay=true`).
9. `Arrived/Ready/Late` создают checkin и обновляют booking.

### Pilot
10. Видит очередь `/pilot/today` по `boat_id/date`.
11. `Start` переводит booking в `in_progress`.
12. `Done` переводит booking в `done`.

## E2E критический сценарий

13. `availability -> booking -> arrived/ready -> start -> done -> kpi today -> drilldown`.
14. `audit_log` содержит цепочку (booking/checkin/status/kpi upsert).
15. RBAC: pilot не может admin-only; marketing_read не может mutate.
16. Нет overbooking при заполненном слоте (`SLOT_FULL`).
17. Ошибки читаемые в UI (без stack trace): `SLOT_FULL`, `BOOKING_NOT_FOUND`, `FORBIDDEN`, `TAB_MISSING`, `COLUMN_MISSING`.
18. Обновления статусов видны обеим ролям без “минутной” задержки.

## Критерий PASS

- Все пункты 1–18 отмечены PASS.
- Нет blocker-дефектов из списка: overbooking, RBAC bypass, missing audit, stale queue.
