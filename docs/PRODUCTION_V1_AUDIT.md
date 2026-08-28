# Ruza / Club Ops production v1 audit

Audit date: 2026-08-28
Current release candidate: `v1.0.0-rc.8`
Current PR: `https://github.com/YaroslavValeev/Ruza/pull/4`

## Executive status

Ruza is ready for a controlled local pilot and staging preparation.
Ruza is not production v1 yet because production-only gates still require external access and real-world proof:
HTTPS production, real OTP provider, Timeweb staging/prod rollout, backup restore into a separate spreadsheet, alerting, iOS Safari smoke, and one real shift without P0 incident.

## Subagent ownership map

| Area | Owner | Current status | Next proof |
|---|---|---|---|
| Git / Release | Release lead | PASS local/PR | Merge PR only after final review, tag final release |
| Backend | Backend lead | PASS local/CI | Staging smoke on deployed URL |
| Frontend / Mobile UX | Frontend lead | PARTIAL | Android and iOS Safari smoke evidence |
| Integrations | Integrations lead | PARTIAL | Site/TG intake schedule enabled in production |
| Data / Google Sheets | Data lead | PASS local/live-local | Backup restore-test to separate sheet |
| Security / Auth | Security lead | PARTIAL | Real OTP provider and HTTPS cookie in staging/prod |
| QA / E2E | QA lead | PASS local/CI | Staging and production E2E |
| DevOps / Timeweb | DevOps lead | PARTIAL | Timeweb staging, monitoring, rollback drill |
| Operations / SOP | Ops lead | PASS docs | Dry-run and real shift sign-off |
| Privacy | Privacy lead | PARTIAL | Production privacy/security acceptance |

## Letter compliance matrix

| Requirement | Status | Evidence | Remaining action |
|---|---|---|---|
| Сверить local / GitHub main / PR / WIP | PASS | `scripts/production-v1-local-audit.ps1` verifies local HEAD, PR #4 head, GitHub CI and merge state | Keep PR updated until merge |
| Не потерять полезные изменения | PASS | All current work is committed in PR #4; working tree clean before this audit update | Re-run clean-tree guard before deploy |
| Разделить изменения на логические PR | PARTIAL | Current production-v1 work is in one draft PR #4 | If reviewer requests smaller slices, split before merge |
| Получить release candidate SHA | PASS | Tag `v1.0.0-rc.8` must point at the same HEAD verified by `scripts/production-v1-local-audit.ps1` | Create final tag after merge |
| Вернуть полный test gate | PASS | GitHub checks `api-tests`, `dashboard-build`, `production-env-guard-linux`, `production-env-guard-windows`, `clean-release-tree-guard-linux`, `clean-release-tree-guard-windows` green on PR #4; local pytest/build commands are documented | Re-run after each commit |
| Запретить production deploy из dirty tree | PASS | `scripts/server/assert-clean-release-tree.sh`; `scripts/server/assert-clean-release-tree.ps1`; `scripts/test-clean-release-tree.ps1`; `scripts/server/test-clean-release-tree.sh`; deploy script calls Linux guard before `docker run` | Use guard in Timeweb deploy path |
| Запретить production deploy с debug/local env | PASS | `scripts/validate-production-env.ps1`; `scripts/server/validate-production-env.sh`; `scripts/test-production-env-guards.ps1`; `scripts/server/test-production-env-guards.sh`; `deploy-api.sh` calls env guard before `docker run` | Fill real `.env.docker` and run guard on Timeweb |
| Intake from site / Telegram / public / manual into one operational intake | PARTIAL | `apps/api/app/services/intake.py`; `POST /public/booking-request`; `POST /intake/sync`; docs `INTAKE_SYNC.md` | Enable real site/TG writers and production scheduler |
| Intake fields exist | PASS | `packages/sheets/schema.py` requires `external_source`, `external_record_id`, `received_at`, `sync_status`, `sync_error`, `converted_booking_id` in `leads` | Keep schema preflight green |
| Duplicate external delivery does not duplicate lead | PASS | `apps/api/tests/test_contract_intake.py`; `scripts/intake-e2e-local.ps1` live/local proof | Run production proof after deployment |
| Real OTP delivery | PARTIAL | `apps/api/app/services/otp_delivery.py` supports phone webhook and Telegram fallback; production config rejects manual OTP | Configure real `OTP_DELIVERY_WEBHOOK_URL` and token |
| Secure cookie / HTTPS / CORS / session expiry / logout / audit | PARTIAL | Production config requires secure cookie; CORS env supported; auth routes write audit; local session/logout tests exist | Prove under HTTPS staging/prod |
| Rate limiting login | PASS local | Auth code rate-limit settings and tests in auth contract suite | Verify on production logs |
| Payment ledger | PASS local | `payments` and `payment_closures` schema, API routes, service, tests | Decide real payment methods/process for staff |
| KPI does not count booking price as paid revenue | PASS local | `test_contract_payments.py::test_payment_rbac_and_kpi_real_money` asserts unpaid booking has `net_revenue_minor=0` and paid/refund values come from `payments` | Re-run on staging with real sheet |
| Staging then production | BLOCKED_EXTERNAL | Timeweb runbooks exist | Requires Timeweb access and owner GO |
| Preflight / smoke | PASS local | `scripts/preflight-local.ps1`; `scripts/smoke-local.ps1` | Run on staging/prod URLs |
| Backup | PASS dry-run | `scripts/backup-sheets.ps1` | Schedule production backup |
| Restore-test | BLOCKED_EXTERNAL | `scripts/restore-sheets-backup.ps1` supports dry-run and explicit write restore | Requires separate target spreadsheet |
| Monitoring / alerting | PARTIAL | Local health/status scripts and UI health badge exist | Add production uptime/alert channel |
| Rollback drill | PARTIAL | Clean deploy script and rollback docs/runbook exist | Execute on staging |
| Dry-run shift | PASS local | Smoke and manual local mobile checks exercised core flow | Repeat with final staging SHA |
| Controlled real shift | BLOCKED_EXTERNAL | SOP/runbook exists | Requires real date, staff, and business GO |
| Android and iOS Safari | PARTIAL | Android LAN smoke was manually verified by owner | iOS Safari must be checked on HTTPS staging/prod |

## Current go/no-go

### Local controlled pilot

GO if:
- `preflight-local.ps1 -Date <season date>` returns `blockers=0`;
- `smoke-local.ps1 -Date <season date>` returns `SUMMARY failures=0`;
- operator, pilot and admin can log in locally;
- Google Sheets tabs stay green.

### Production v1

NO-GO until:
- PR #4 is reviewed, merged, and final tag is created;
- production/staging is available over HTTPS;
- real OTP delivery is configured and tested;
- intake sync runs from real site/TG sources without duplicates;
- paid revenue reconciliation is tested on real data;
- backup restore-test, monitoring, alerting and rollback drill are complete;
- Android and iOS Safari pass the main scenario;
- one real shift completes without P0.

## Commands for final local proof

From repository root:

```powershell
git status --short --branch
powershell -ExecutionPolicy Bypass -File .\scripts\server\assert-clean-release-tree.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\validate-production-env.ps1 -EnvFile .\.env.docker
powershell -ExecutionPolicy Bypass -File .\scripts\preflight-local.ps1 -Date 2026-06-01 -ApiPort 8001
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-local.ps1 -Date 2026-06-01 -ApiPort 8001
powershell -ExecutionPolicy Bypass -File .\scripts\intake-e2e-local.ps1
```

From `icebeach-wakeclub`:

```powershell
python -m pytest -q
cd .\apps\dashboard
npm run build
```

## Owner actions before production v1

1. Choose OTP provider and issue production webhook credentials.
2. Confirm Timeweb deployment mode: App Platform or VPS.
3. Provide staging/prod domains.
4. Provide a separate Google Spreadsheet for restore-test.
5. Confirm real site/TG intake writer ownership and schedule.
6. Run Android and iOS Safari smoke on HTTPS.
7. Pick dry-run and first real-shift dates.
