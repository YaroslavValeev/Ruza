# Enterprise Change Log

## 2026-04-18

- Added Phase-0 technical smoke script: `scripts/sheets_smoke_rw.py`.
- Verified repo hygiene: `secrets/service-account.json` is ignored by `.gitignore` and not tracked by git.
- Added execution checklist to close Phase 0 with a real `read/write` proof in `audit_log`.

## Pending completion

- None for Phase 0 (operator confirmed completion).

## 2026-04-18 (Phase 0 status confirmation)

- Confirmed by operator: Google Sheet PRO v1 is created with required tabs/headers.
- Confirmed by operator: service account has Editor rights and RW smoke passed.
- Locked planning inputs for delivery: `boats_count=1`, `mvp_target_date=2026-05-15`.
- Added phase-by-phase execution contract in `docs/ROADMAP_CONTRACT.md`.

## 2026-04-18 (Roadmap contract v2)

- Reworked `docs/ROADMAP_CONTRACT.md` into a 5-week MVP execution plan to 2026-05-15.
- Added Release Gates (RBAC/audit/capacity/pilot queue/KPI definitions).
- Added Week 1 PR acceptance criteria and explicit DoD per week.


## 2026-04-18 (Week 2 readiness hardening)

- Added Week 2 execution plan with strict step-by-step sequence in `docs/WEEK2_EXECUTION_PLAN.md`.
- Added API hardening: unified error codes, schema-check endpoint, CORS allowlist, stronger token payload (`iat` + `exp` + `staff_user_id` + `role`).
- Added booking/availability services with idempotency and SLOT_FULL protection + contract tests using mock Sheets wrapper.


## 2026-04-18 (Week 3 implementation start)

- Added backend check-in, pilot queue, and booking status transition services/endpoints.
- Added Week 3 contract tests (`test_ops_week3.py`) for check-in/audit, pilot queue readiness, and role transition guard.
- Added operator and pilot UI controls for check-in/start/done workflows.
- Added UI proof artifacts under `docs/screenshots/` and linked them from Week 2 plan.
- Added `docs/WEEK3_EXECUTION_PLAN.md` with Gate-check and cutline.


## 2026-04-18 (Week 4 KPI start)

- Added KPI endpoints (`/kpi/today`, `/kpi/week`, `/kpi/month`) and drilldown endpoint (`/kpi/drilldown`).
- Added analytics_daily on-demand upsert + audit write on today KPI calculations.
- Added KPI contract tests (`test_kpi_week4.py`) with mock Sheets data.
- Added KPI UI cards + drilldown view in dashboard.
- Added `docs/WEEK4_EXECUTION_PLAN.md` with cutline and acceptance checks.


## 2026-04-18 (Week 5 launch readiness pack)

- Added launch smoke checklist: `docs/WEEK5_LAUNCH_CHECKLIST.md` (18-point PASS flow).
- Added operations docs: `docs/OPS_RUNBOOK.md`, `docs/TROUBLESHOOTING.md`, `docs/PILOT_RUN_DAY1.md`.
- Added admin diagnostics endpoint `/ops/diagnostics` (tabs health + cache TTL + app version).
- Added UI UX accelerators: today/tomorrow quick actions and user-friendly error messages.
