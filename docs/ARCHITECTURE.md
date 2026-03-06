# Architecture — Ice Beach Wake Club Automation (Greenfield)

## Goals (MVP)
1) Google Sheets = Source of Truth
2) Web Dashboard (React cards) for Admin/Operator/Pilot/Coach
3) Booking engine + KPI endpoints
4) On-device Voice Admin prototype + phone check-in
5) Multiclub-ready schema (club_id everywhere)

## Proposed Stack
- Backend: Python (FastAPI recommended)
- Frontend: React + Vite + Tailwind
- Sheets: Google Sheets API (service account)
- Auth: role-based (staff_users in Sheets)
- Edge: on-device voice (optional face later)

## Role Views
- Admin: everything
- Operator: bookings + clients + check-ins
- Pilot: boat queue + statuses
- Coach: own sessions + notes
- Marketing-read: KPI and marketing read-only
