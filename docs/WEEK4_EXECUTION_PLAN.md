# Week 4 Execution Plan — KPI Cards + Drilldown + analytics_daily

## Goal

Дать управленческую видимость по смене/неделе/месяцу: KPI карточки + drilldown до booking-строк.

## Backend Deliverables

1. KPI endpoints:
- `GET /kpi/today?today=YYYY-MM-DD`
- `GET /kpi/week?today=YYYY-MM-DD`
- `GET /kpi/month?today=YYYY-MM-DD`

2. Drilldown endpoint:
- `GET /kpi/drilldown?period=today|week|month&metric=...&today=YYYY-MM-DD`

3. Metrics (minimum):
- `utilization_pct`
- `revenue_estimate`
- `coach_attach_rate`
- `no_show_rate`
- `new_clients_count`

4. analytics_daily upsert:
- on-demand upsert for `/kpi/today`
- audit entry for `entity=analytics_daily`

## UI Deliverables

- KPI screen with cards for selected period.
- Click card -> drilldown list of bookings.
- `today` as default date.

## Tests

- Empty day -> KPI zeros.
- Done booking contributes to revenue/utilization.
- No show affects `no_show_rate`.
- Drilldown returns expected booking rows.

## Week 4 Cutline

- No marketing/forecast.
- No voice/face work.
- No big BI redesign.
