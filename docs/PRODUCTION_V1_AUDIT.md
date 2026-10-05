# Ruza / Club Ops production v1 audit

Audit date: 2026-10-05
Current release (main tip): `bd77c197` — Merge PR #7 (`ruza/access-timezone-admin-rides`)
Previous release candidate tag: `v1.0.0-rc.19` → `51180f3` (behind main; do not treat as production tip)
Stale PR #1: closed as `not_planned` by AGM (historical only)

## Executive status

Ruza **main** includes PR #7: access limits, phone rate-limit, timezone handling, admin ride timer, Telegram OTP allowed in production when `TELEGRAM_BOT_TOKEN` is set (SMS webhook may be empty), and CI `npm audit --omit=dev --audit-level=low`.

Production VPS exists and runs docker compose at `/opt/icebeach` (`icebeach-api-1`, `icebeach-dashboard-1`), detached clean at `bd77c197` — **this audit does not authorize a new deploy**.

Ruza is ready for controlled local pilot and VPS operations discipline.
Ruza is **not** Cash-cow 10/10 / full production v1 GO until remaining **EXTERNAL** gates below are proven by the Owner (or designated operator) on real HTTPS + real shift data.

Out of scope: Turism. Do not rotate secrets in this docs pass. Do not merge this PR to main from an agent; Owner decides. Do not deploy from this PR.

## What landed in PR #7 (on main)

| Area | Status on main |
|---|---|
| Access limits / phone rate-limit | In code + tests |
| Timezone / local shift date behavior | In code + tests |
| Admin ride timer | In code + dashboard |
| Telegram OTP in production | Allowed when `TELEGRAM_BOT_TOKEN` set; phone webhook optional |
| CI dashboard audit | `npm audit --omit=dev --audit-level=low` |
| Production env guards | Accept Telegram OTP path OR HTTPS webhook |

## Subagent ownership map

| Area | Owner | Current status | Next proof |
|---|---|---|---|
| Git / Release | Release lead | PASS on main `bd77c197` | Optional annotated tag `v1.0.0-rc.20` on main tip after Owner GO; open docs PR only |
| Backend | Backend lead | PASS local/CI | Staging/prod smoke on deployed URL after Owner deploy GO |
| Frontend / Mobile UX | Frontend lead | PASS local / PARTIAL external | Android and iOS Safari smoke evidence on HTTPS |
| Integrations | Integrations lead | PARTIAL | Site/TG intake schedule enabled and proven live |
| Data / Google Sheets | Data lead | PASS local/live-local | Backup restore-test to separate spreadsheet |
| Security / Auth | Security lead | PARTIAL → Telegram path available | Prove Telegram OTP (or HTTPS SMS webhook) under production HTTPS cookies |
| QA / E2E | QA lead | PASS local/CI | Staging and production E2E |
| DevOps / VPS | DevOps lead | PARTIAL (compose VPS live) | HTTPS proof, healthcheck schedule, monitoring, rollback drill — Owner GO only |
| Operations / SOP | Ops lead | PASS docs | Dry-run and real shift sign-off |
| Privacy | Privacy lead | PARTIAL | Production privacy/security acceptance |

## Letter compliance matrix

| Requirement | Status | Evidence | Remaining action |
|---|---|---|---|
| Сверить local / GitHub main / PR / WIP | PASS | main tip `bd77c197` = Merge PR #7 | Keep docs branches rebased on `origin/main` |
| Не потерять полезные изменения | PASS | PR #7 merged; working tree policy unchanged | Re-run clean-tree guard before any deploy |
| Разделить изменения на логические PR | PASS for code slice | PR #7 merged; this docs PR is plan-only | Keep Turism and unrelated product slices out |
| Получить release candidate SHA | PASS main / TAG lag | Tag `v1.0.0-rc.19` points at `51180f3` (behind main) | Owner may create `v1.0.0-rc.20` on `bd77c197` (optional; not done in this docs PR unless explicitly allowed) |
| Вернуть полный test gate | PASS | GitHub CI jobs including dashboard `npm audit --omit=dev` | Re-run after each commit |
| Запретить production deploy из dirty tree | PASS | clean-tree guards + deploy scripts | Use guard on VPS path |
| Запретить production deploy с debug/local env | PASS | env guards accept Telegram OTP **or** HTTPS webhook | Keep `ALLOW_MANUAL_OTP_DELIVERY=false` in production |
| Доказать staging/prod URL до GO | PASS local / **EXTERNAL** | staging-proof scripts validate behavior without side effects | Run proof against real HTTPS URL |
| Monitoring healthcheck готов к установке | PASS local / **EXTERNAL** | healthcheck script + CI guard | Install on VPS scheduler + real alert channel |
| Intake from site / Telegram / public / manual | PARTIAL | intake service + public booking-request + sync docs | Enable real writers and production schedule |
| Duplicate external delivery does not duplicate lead | PASS | contract + local e2e | Production proof after deploy |
| Real OTP delivery | PARTIAL → Telegram path on main | `otp_delivery.py` + production config: webhook **or** `TELEGRAM_BOT_TOKEN` | Prove delivery for staff with `telegram_id` (webhook may be empty) |
| Secure cookie / HTTPS / CORS / session | PARTIAL / **EXTERNAL** | production config requires secure cookie | Prove under HTTPS |
| Rate limiting login | PASS local | phone rate-limit service + auth tests | Verify on production logs |
| Payment ledger | PASS local | payments schema/API/tests; Owner: manual Sheets ledger only | Keep SOP aligned; no provider in v1 |
| KPI paid revenue from payments | PASS local | contract test | Re-run on staging with real sheet |
| Staging then production | **EXTERNAL** | VPS compose at `/opt/icebeach` already used | Owner GO for checkout/tag/rebuild; no agent deploy |
| Preflight / smoke | PASS local | preflight + smoke scripts | Run on staging/prod URLs |
| Backup | PASS dry-run | backup script | Schedule production backup |
| Restore-test | PASS local / **EXTERNAL** | restore dry-run + write guard | Separate target spreadsheet for real `-Write` |
| Monitoring / alerting | PARTIAL / **EXTERNAL** | healthcheck can POST alerts | Install scheduler + connect channel |
| Rollback drill | PASS local / **EXTERNAL** | rollback script dry-run/execute | Execute on staging with Owner GO |
| Mobile/PWA readiness | PASS local / **EXTERNAL** | mobile readiness guards in CI | Real iOS Safari HTTPS smoke |
| Dry-run shift | PASS local | local mobile checks | Repeat with final staging SHA |
| Controlled real shift | **EXTERNAL** | SOP exists | Real date, staff, business GO |
| Android and iOS Safari | PARTIAL / **EXTERNAL** | Android LAN smoke by Owner historically | iOS Safari on HTTPS |

## Current go/no-go

### Local controlled pilot

GO if:
- `preflight-local.ps1 -Date <season date>` returns `blockers=0`;
- `smoke-local.ps1 -Date <season date>` returns `SUMMARY failures=0`;
- operator, pilot and admin can log in locally;
- Google Sheets tabs stay green.

### Production v1 / Cash-cow 10/10

NO-GO until **EXTERNAL** gates:
- HTTPS production (or staging) URL proven with `staging-proof`;
- Telegram OTP (or HTTPS SMS webhook) proven for real staff phones/`telegram_id`;
- intake sync from real site/TG sources without duplicates;
- paid revenue reconciliation on real data;
- backup restore-test, scheduled monitoring, alerting, rollback drill;
- Android and iOS Safari main scenario;
- one real shift without P0;
- Owner GO for any new tag/deploy (agents must not deploy).

## Commands for final local proof

From repository root:

```powershell
git status --short --branch
powershell -ExecutionPolicy Bypass -File .\scripts\server\assert-clean-release-tree.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\validate-production-env.ps1 -EnvFile .\.env.docker
powershell -ExecutionPolicy Bypass -File .\scripts\preflight-local.ps1 -Date 2026-06-01 -ApiPort 8001
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-local.ps1 -Date 2026-06-01 -ApiPort 8001
powershell -ExecutionPolicy Bypass -File .\scripts\intake-e2e-local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test-staging-proof.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test-mobile-readiness.ps1
```

From `icebeach-wakeclub`:

```powershell
python -m pytest -q
cd .\apps\dashboard
npm run build
npm audit --omit=dev --audit-level=low
```

## Owner actions before production v1 GO

1. Confirm OTP path in production: `TELEGRAM_BOT_TOKEN` (webhook may be empty) **or** HTTPS SMS webhook + token.
2. Confirm VPS docker compose at `/opt/icebeach` remains the primary deploy path (Timeweb App Platform optional).
3. Provide/confirm staging/prod HTTPS domains.
4. Provide a separate Google Spreadsheet for restore-test.
5. Confirm real site/TG intake writer ownership and schedule.
6. Run Android and iOS Safari smoke on HTTPS.
7. Pick dry-run and first real-shift dates.
8. Optionally tag `v1.0.0-rc.20` on `bd77c197` after docs merge — Owner only.
