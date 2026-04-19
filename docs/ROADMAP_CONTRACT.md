# Контракт на результат — MVP до 15 мая 2026 (Айс пляж, Руза)

## 0) Факты и ограничения (фиксированные)

1. Source of Truth: **Google Sheets** по схеме **PRO v1**.
2. CRM не используем.
3. Dashboard обязателен: KPI cards + bookings CRUD + pilot screen.
4. Стек MVP: **FastAPI (Python)** + **React/Vite/Tailwind**.
5. RBAC обязателен на backend: `admin`, `operator`, `pilot`, `coach`, `marketing_read`.
6. Voice — позже (on-device), в MVP обязателен fallback по телефону.
7. Face recognition — только позже, опционально, on-device и по consent.
8. Git-политика: commit разрешён, push блокируется pre-push hook.
9. OpenAI API в коде не используется.
10. Spreadsheet ID: `1Jos8absjdLueLoWXZDJS67PRHXfrQ-fnTq-yiXk2_18`.
11. Локальный контур: Windows 10, диск E:.
12. Плановые входы: `boats_count=1`, `mvp_target_date=2026-05-15`.
13. Фаза 0 подтверждена закрытой (RW smoke PASS, service account Editor, PRO v1 Sheet готов).

Единые документы правды:

- `docs/ROADMAP_CONTRACT.md`
- `README.md`
- `docs/enterprise/19_CHANGELOG.md`

## 1) Цель MVP (DoD к 15 мая 2026)

Должен стабильно работать end-to-end процесс смены:

1. Operator создаёт/редактирует бронь (`bookings`) с записью в `audit_log`.
2. Check-in по телефону (`checkins`) обновляет готовность клиента.
3. Pilot видит очередь по `boat_id`, включая `ready/late`.
4. Pilot переводит сессию `in_progress -> done`.
5. KPI cards (`today/week/month`) отражают факт и drilldown.
6. Каждая мутация пишет `audit_log`.
7. Overbooking невозможен (capacity enforcement).

## 2) Release Gates (обязательные стоп-краны)

- **Gate A:** RBAC enforced на backend (не только UI).
- **Gate B:** `audit_log` на каждую мутацию (create/update/cancel/checkin/override).
- **Gate C:** no overbooking + idempotent `booking_id`.
- **Gate D:** pilot queue всегда корректна по `boat_id/date/time/status`.
- **Gate E:** KPI definitions совпадают с `docs/KPI.md`.

## 3) Пятинедельный план до 15 мая 2026

### Неделя 1 — Sprint 0: Foundation

**Deliverables:**

- Repo skeleton: `apps/api`, `apps/dashboard`, `packages/sheets`, `scripts`, `docs`, `.githooks`.
- `packages/sheets`: `read_tab`, `append_row`, `update_by_id`, `find`, schema-check, `write_audit`.
- API baseline: `/health`, signed session auth, RBAC middleware, базовые pydantic контракты.
- Dashboard baseline: login, route guards, shells (KPI/Operator/Pilot).

**DoD:**

- Backend стартует, `/health` отвечает.
- Dashboard стартует, login/roles работают.
- Backend RBAC блокирует неразрешённые действия.
- Тестовая мутация оставляет запись в `audit_log`.

### Неделя 2 — MVP Ops 1: Availability + Booking Create

**Deliverables (API/UI):**

- `GET /availability?date=YYYY-MM-DD` с учётом schedule/overrides/bookings/capacity.
- `POST /bookings` с idempotency и повторной capacity-проверкой перед append.
- Operator UI: выбор даты/слота, создание брони, фильтры `date/status/boat_id`.

**DoD:**

- Capacity не нарушается.
- Повторный POST с тем же `booking_id` не создаёт дубль.
- `audit_log` содержит create booking.

### Неделя 3 — MVP Ops 2: Check-in + Pilot Queue

**Deliverables (API/UI):**

- `POST /checkins` (`phone/manual`, `arrived/ready/late`) + синхронизация booking status.
- `GET /pilot/today?boat_id=...&date=...` (очередь по времени, ready/late).
- `PATCH /bookings/{id}` для `in_progress`, `done`, `no_show`.
- UI: one-click controls для operator/pilot.

**DoD:**

- Pilot очередь прозрачна и корректна.
- Operator меняет готовность в 1 клик.
- Каждая операция трассируется в `audit_log`.

### Неделя 4 — MVP Ops 3: KPI + Drilldown + Daily Snapshot

**Deliverables:**

- `/kpi/today`, `/kpi/week`, `/kpi/month`.
- Минимальные KPI: `utilization_pct`, `revenue_estimate`, `coach_attach_rate`, `no_show_rate`, `new_clients_count`.
- Обновление `analytics_daily` (on-demand допустим для MVP).
- KPI UI cards + drilldown по вкладу бронирований.

**DoD:**

- KPI соответствуют формулам в `docs/KPI.md`.
- Drilldown позволяет вручную проверить расчёт.
- Snapshot в `analytics_daily` обновляется стабильно.

### Неделя 5 — Stabilization / Launch Readiness

**Deliverables:**

- Smoke checklist по ролям.
- Регресс ключевого сценария (`booking -> checkin -> pilot -> done -> KPI`).
- UX-ускорения: today-by-default, быстрые фильтры, минимум кликов.
- Док запуска/диагностики (`docs/DEPLOY_LOCAL.md`).

**DoD:**

- Система держит 1 реальную смену без разработчика рядом.
- Ошибки логируются без утечки ПДн.
- Процесс понятен operator/pilot.

## 4) Backlog по темам

### A. Данные / Sheets

- Schema-check вкладок и заголовков PRO v1.
- Валидация справочников (`clubs`, `boats`, `staff_users`, `pricing`).
- Idempotency `booking_id`.
- Унифицированный writer в `audit_log`.
- Updater `analytics_daily`.

### B. Backend (FastAPI)

- RBAC middleware + permissions matrix.
- Availability engine (`schedule + overrides - bookings`).
- Bookings create/update/cancel/status transitions.
- Checkins + late rules.
- Pilot endpoints (`today/next`) параметризованно по `boat_id`.
- KPI endpoints + drilldown data.
- Человекочитаемые error models.
- Тесты: mock SheetWrapper + контрактные API тесты.

### C. Frontend (React)

- Login + role routes.
- Operator view: slots/bookings/check-in controls.
- Pilot view: queue + status controls + readiness badges.
- KPI cards + drilldown.
- UX defaults для скорости в смене.
- Только backend API, без прямых вызовов Sheets из браузера.

### D. Ops / DevEx

- `scripts/run_api`, `scripts/run_dashboard`, `scripts/install_hooks`.
- `.env.example`, `.gitignore` для `secrets` и `artifacts`.
- Маскирование ПДн в логах.
- `docs/DEPLOY_LOCAL.md` для запуска за 5 минут.

## 5) Ожидаемый ближайший PR (Week 1)

PR #1 должен включать:

- repo skeleton FastAPI/React,
- SheetWrapper + schema-check + audit writer,
- backend RBAC middleware,
- dashboard login (через `staff_users`),
- `/health`,
- минимальный smoke сценарий + команды запуска.

Критерий приёмки PR #1:

- локальный запуск без ручных обходов,
- вход как admin работает,
- backend RBAC блокирует доступ pilot к admin-функциям.
