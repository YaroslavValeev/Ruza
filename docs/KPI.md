# KPI Definitions (v1)

## Utilization %
= (sessions_done / (available_slots_capacity)) * 100

## Revenue Estimate
= sum(bookings.total_price where status in done/confirmed/checked_in/in_progress within period)

## Coach Attach Rate %
= (count(bookings where coach_required=true) / total bookings) * 100

## No-show Rate %
= (count(status=no_show) / total bookings) * 100

## NPS Avg
= average(feedback.nps) for period

## API → UI mapping

| Endpoint | UI |
|----------|-----|
| `GET /kpi/summary?period=day` | KpiPage cards (day) |
| `GET /kpi/summary?period=week` | KpiPage cards (week) |
| `GET /kpi/summary?period=month` | KpiPage cards + plan_fact bars |
| `POST /analytics/snapshot?date=` | admin button on KpiPage |
| `GET /marketing/funnel` | MarketingPage funnel |
| `GET /preflight/summary` | KpiPage admin block |
| `POST /smoke/run` | KpiPage admin block |

## Plan vs Fact

Targets from `kpi_targets` tab (`period` = `YYYY-MM` or `YYYY-WW`).
Returned in `kpi.summary.plan_fact`:
- `sessions_pct`, `utilization_pct_of_target`, `revenue_pct`
