# Ruza scenario verification

Date: 2026-10-11 (Europe/Moscow). Baseline: `1256d9016eb45e04343670eaf06d5fec2ea9fe40`.

Deployment card: Club Box/Ruza CRM -> local QA / release candidate -> local Windows;
S1 mywave-bot-server is the existing deployment recorded by main's runbooks -> QA
worktree; observed VPS checkout `/opt/icebeach` -> YaroslavValeev/Ruza -> loopback
QA URLs; recorded public URL `https://ruza.mywavewake.ru` -> in-memory QA data;
existing Google Sheets / backup tooling retained. No new VPS, DB or Compose project.
The `/opt/icebeach` placement in newer release documentation differs from the
September infrastructure card's TBD state; this pass does not silently redefine
the architecture or independently establish server state.

## Roles and verified behavior

| Role | Checks |
| --- | --- |
| Operator | Arrival, warmup, explicit pilot handoff, duplicate client/booking/intake, payment capture |
| Pilot | Assigned boat, start/pause/stop, duplicate controls, blocked second live ride, slot-extension races |
| Administrator | Ride controls, split payment, refunds, daily close and KPI reconciliation |
| Coach / marketing | Read/write access matrix, assigned coach sessions, no writes on denied requests |
| Integrations / operations | Telegram success/failure/manual-required, retry, reminders CLI and scheduler contracts |
| QA / security | Lost acknowledgements, role demotion, cross-club IDs, browser exceptions, dates, dependencies |

The expanded role suite reproduced ten failures on the baseline. Fixes scope live
focus to the coach/assigned pilot, reject conflicting/cross-club booking IDs,
normalize domestic Russian phone numbers, recover missing payment audit records,
validate combined preparation before writes and serialize boat/slot mutations.
Telegram `sent_at` and sent counters now require confirmed delivery. Unavailable
delivery stays retryable and is recorded explicitly in audit.

## Evidence

- Native API suite: **262 passed**.
- Current source mounted read-only into cached `ruza-api:latest`, network disabled:
  **257 passed / 5 Windows-only skipped**. This verifies container execution,
  not a fresh build of the production Dockerfile.
- Browser with actual demo API: **7 scenarios passed**: anonymous bootstrap,
  operator handoff, mobile start/countdown, pause/stop, payment/KPI, role scope
  and logout, no unhandled JavaScript errors.
- Isolated frontend regression harness: **100 scenarios passed**, desktop and
  390px mobile, five roles/eight statuses, clock rebasing and duplicate actions.
- Local Moscow date tests: **5 passed**. TypeScript and Vite production build pass.
- Full npm audit: **8 -> 5 high dependency nodes**, all remaining in the build
  tooling chain rooted in unpatched `braces`. Runtime-only audit: **0**.
  See [DEPENDENCY_AUDIT.md](DEPENDENCY_AUDIT.md).
- Fresh Dockerfile build: blocked while fetching base-image metadata
  (`DeadlineExceeded`). HTTPS API and SSH probes from this host timed out.
  These are unavailable external proofs, not proof of an application outage.

Browser evidence is generated in ignored `.runlogs/browser-qa/` and uploaded by
the `dashboard-ui-scenarios` CI job. No real Sheets, OTP recipients or client
payments are used by the local suite. Chromium mobile viewport testing is not
physical Android or iOS Safari acceptance.

## Reproduce

From the repository root:

```powershell
$env:PYTHONPATH=(Resolve-Path icebeach-wakeclub).Path
python -m pytest icebeach-wakeclub/apps/api/tests -q
npm ci --prefix icebeach-wakeclub/apps/dashboard
npm ci --prefix scripts/browser-qa
node scripts/browser-qa/node_modules/playwright/cli.js install chromium
python scripts/run_browser_qa.py
```

QA requires Node 24 (date regression uses its built-in TypeScript stripping).
The runner claims free loopback ports and owns its child handles; it does not
stop unknown processes or load production secrets. Optional `--chromium PATH`
uses an already installed browser. Future runs use the current Moscow date.

## Release limits

`operation_lock` protects only one API process. Keep a single API writer;
multiple workers/replicas or external direct Sheet writes require a shared
transactional coordinator. Do not present finite local races as distributed
exactly-once guarantees. An acknowledged Telegram send followed by a failed
audit/Sheets write can still produce a duplicate on retry.

Before production acceptance: CI on the final candidate SHA, fresh image build,
authenticated HTTPS/OTP, real intake delivery, separate-sheet restore, monitoring
and alert delivery, rollback drill, physical Safari/Android and a controlled real
shift. Recorded old runbook claims are not refreshed runtime evidence.

No production deploy, scheduler activation, live messages, real payments, secret
rotation or merge to main was performed by this verification pass.
