# Architecture — Ice Beach Wake Club Automation (Greenfield)

## Platform placement

Ruza классифицируется как продукт `Club Box/Ruza CRM`. Каноническая карта
MyWave находится в [MYWAVE_INFRASTRUCTURE.md](MYWAVE_INFRASTRUCTURE.md).
Внешний environment, server, canonical folder, domain/API и backup policy для
Ruza пока не утверждены; до утверждения проект остается `NOT DEPLOYED`.

## Goals (MVP)
1) Каноническая MyWave Sheet = Source of Truth для входящих заявок
2) RuzaTab = Source of Truth для операционных данных клуба
3) Web Dashboard (React cards) for Admin/Operator/Pilot/Coach
4) Booking engine + KPI endpoints
5) On-device Voice Admin prototype + phone check-in
6) Multiclub-ready schema (club_id everywhere)

## Proposed Stack
- Backend: Python (FastAPI recommended)
- Frontend: React + Vite + Tailwind
- Sheets: Google Sheets API (service account)
- Auth: role-based (staff_users in Sheets)
- Edge: on-device voice (optional face later)

## Intake flow

`site / Telegram → canonical Ruza tab → intake_sync → RuzaTab.leads → operator confirmation → booking`

Автоматически создавать `booking` из внешней заявки запрещено: доступность,
актуальная цена и экипировка подтверждаются оператором.

## Role Views
- Admin: everything
- Operator: bookings + clients + check-ins
- Pilot: boat queue + statuses
- Coach: own sessions + notes
- Marketing-read: KPI and marketing read-only
