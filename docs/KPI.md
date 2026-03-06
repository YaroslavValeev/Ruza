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
