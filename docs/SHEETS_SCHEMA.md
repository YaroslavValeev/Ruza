# Google Sheets — Source of Truth (PRO v1)

Эта схема — **контракт системы**. Всё приложение (API, dashboard, edge-модули) опирается на неё.

## Spreadsheet
- Spreadsheet ID: {{spreadsheet_id}}
- Service account JSON path (local only): {{service_account_json_path}}

---

## 0) Справочники (нормализация и мультиклуб)
### `clubs`
- club_id (string, unique) — например `ice_beach_ruza`
- club_name
- timezone (e.g. Europe/Moscow)
- is_active (bool)

### `boats`
- boat_id (string, unique)
- club_id
- boat_name
- capacity_default (int)
- pilot_user_id (staff_user_id)
- is_active (bool)

### `staff_users`
- staff_user_id (string, unique)
- club_id
- role (admin|operator|pilot|coach|marketing_read)
- full_name
- phone
- telegram_id
- is_active (bool)
- created_at

### `pricing`
- price_id (string, unique)
- club_id
- valid_from (YYYY-MM-DD)
- base_price (int) — 12000/14000
- coach_price (int) — 3500
- currency (RUB)
- notes

---

## 1) Клиенты и согласия
### `clients`
- client_id (string, unique; recommended UUID)
- club_id
- full_name
- phone (RU)
- telegram_id (optional)
- birthday (optional)
- segment (local|moscow|premium|family|athlete|other)
- consent_face (bool) + consent_face_ts
- consent_voice (bool) + consent_voice_ts
- consent_media (bool) + consent_media_ts
- source_first (utm/referral/offline/partner)
- created_at
- last_seen_at
- notes

### `client_tags`
- client_id
- tag (e.g. `vip`, `injury_knee`, `family_kids`)
- created_at

---

## 2) Расписание и слоты
### `schedule`
- schedule_id (string, unique)
- club_id
- weekday (0-6)
- time (HH:MM)
- boat_id
- capacity (int)
- is_active (bool)
- notes

### `slot_overrides`
- slot_id (string, unique)
- club_id
- date (YYYY-MM-DD)
- time (HH:MM)
- boat_id
- capacity (int)
- status (active|closed|private)
- reason

---

## 3) Записи / сессии
### `bookings`
- booking_id (string, unique, idempotent)
- club_id
- client_id
- date (YYYY-MM-DD)
- time (HH:MM)
- boat_id
- coach_required (bool)
- coach_user_id (staff_user_id, optional)
- status (confirmed|checked_in|in_progress|done|cancelled|no_show)
- price_base (int)
- price_coach (int)
- discount (int, optional)
- total_price (int) — computed
- created_by (staff_user_id or `client`)
- created_at
- updated_at
- notes

### `checkins`
- checkin_id (string, unique)
- club_id
- booking_id
- client_id
- method (phone|manual|face)
- status (arrived|ready|late|cancelled)
- ts
- operator_user_id (optional)

---

## 4) Сервис: отзывы, инциденты, качество
### `feedback`
- feedback_id (string, unique)
- club_id
- booking_id
- client_id
- nps (0-10)
- rating (1-5)
- text
- ts

### `incidents`
- incident_id (string, unique)
- club_id
- date
- severity (low|medium|high)
- category (safety|equipment|service|weather)
- description
- resolved (bool)
- resolved_ts

---

## 5) Маркетинг и лиды (без CRM)
### `leads`
- lead_id (string, unique)
- club_id
- full_name
- phone
- source (instagram|vk|referral|offline|partner|ads)
- utm_source
- utm_campaign
- status (new|contacted|booked|lost)
- created_at
- notes

### `campaigns`
- campaign_id (string, unique)
- club_id
- name
- channel (instagram|vk|tg|offline|partner|ads)
- start_date
- end_date
- budget (int)
- target_leads (int)
- target_cac (int)
- notes

### `utm_events`
- event_id (string, unique)
- club_id
- ts
- event_type (visit|lead_submit|call_click|book_click)
- utm_source
- utm_campaign
- page
- anon_id (optional)

---

## 6) Аналитика, KPI, прогнозы
### `kpi_targets`
- target_id (string, unique)
- club_id
- period (YYYY-MM) or (YYYY-WW)
- sessions_target (int)
- utilization_target_pct (int)
- revenue_target (int)
- coach_attach_target_pct (int)
- notes

### `analytics_daily`
- date (YYYY-MM-DD)
- club_id
- sessions_count
- utilization_pct
- revenue_estimate
- coach_attach_rate
- new_clients_count
- repeat_rate_30d
- nps_avg
- no_show_rate
- leads_count
- cac_estimate
- notes

### `forecast_monthly`
- period (YYYY-MM)
- club_id
- sessions_forecast
- utilization_forecast_pct
- revenue_forecast
- assumptions_json
- updated_at

---

## 7) Аудит
### `audit_log`
- ts
- actor (staff_user_id|system)
- action (create|update|cancel|override)
- entity (client|booking|slot|lead|campaign)
- entity_id
- diff_json

---

## MVP обязательные листы
`clubs, boats, staff_users, pricing, clients, schedule, bookings, audit_log, analytics_daily`.
