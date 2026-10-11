# Shift Reminders Operations

## Scope and Placement

`shift_reminders` invokes the existing `run_shift_reminders()` runner, which
posts to `POST /internal/agents/shift-reminders` using `X-Agents-Secret`.
The API owns club timezone, reminder windows, delivery and deduplication.
No notification, timer, frontend, schema, port or Compose changes belong to
this integration. This command is NOT a dry run: a configured API may write
Sheets and send real notifications.

MyWave placement: **Club Box / Ruza CRM -> existing VPS / Compose runtime ->
existing `/opt/icebeach` checkout -> `YaroslavValeev/Ruza` -> existing API ->
existing RuzaTab / Sheets backup**. Do not create a new VPS, Compose project,
database, top-level deployment directory or Telegram polling process.
The `tourism` product is separate and out of scope; use `tourism`, not
`toutism`, in new names. Preserve existing `IceBeach-Agent-*` task names.

Placement evidence comes from [RELEASE_PLAN.md](../RELEASE_PLAN.md),
[SERVER_COMMANDS.md](../SERVER_COMMANDS.md) and
[PRODUCTION_V1_GATES.md](../PRODUCTION_V1_GATES.md), updated 2026-10-07.
These supersede the older placement-pending infrastructure notes. The
dedicated infrastructure canon file is absent from this checkout; confirm
placement with the Owner before activation rather than inventing another
server assignment. Live host state has NOT been verified by this change.

## Local Verification Without External I/O

Run in **local PowerShell**, only from the QA worktree:

```powershell
Set-Location 'F:\Проекты MyWave\NEW2026\Ruza-qa-20261010'
python -m pytest icebeach-wakeclub/apps/api/tests/test_contract_agent_cli.py -q
```

Tests mock runner dispatch, HTTP transport, API service and all Task
Scheduler cmdlets; the API contract uses in-memory Sheets. Network access
and notification calls are blocked in these tests. No task registration,
live API, Telegram, SMS or Google access is needed. PowerShell contracts are
skipped when neither `pwsh` nor `powershell` is available.

`python -m apps.agents.cli list` is read-only when executed from
`icebeach-wakeclub`; it lists `shift_reminders` without running any agent.
Do not run `run --agent shift_reminders` or `scripts/agents-smoke.ps1`
against a configured live API during QA. There is no CLI `--dry-run` flag.

For an isolated **local Docker** check, build the existing API Dockerfile
without production env files or secrets, then run tests with networking
disabled and the API server NOT started:

```powershell
Set-Location 'F:\Проекты MyWave\NEW2026\Ruza-qa-20261010'
docker build -f icebeach-wakeclub/Dockerfile -t ruza-reminders-contract-local icebeach-wakeclub
docker run --rm --network none --workdir /app --entrypoint python ruza-reminders-contract-local -m pytest apps/api/tests/test_contract_agent_cli.py -q
```

The image build needs package-registry access; no production integration
is involved. Docker Linux tests skip PowerShell-specific contracts, which
must pass separately on Windows. No Compose project or DB is started.

## Windows Scheduler Integration (Owner Activation Only)

The existing `scripts/schedule-agents.ps1` now includes
`IceBeach-Agent-ShiftReminders` running
`scripts/run-agent.ps1 -Agent shift_reminders` once per minute, all day.
A **daily midnight trigger** renews the 24-hour repetition period; a
one-time trigger would stop after day one. The API determines the club's
local day, not the scheduler host timezone. `IgnoreNew` prevents overlapping
instances of this task; execution is limited to three minutes. Other agents'
existing schedules are unchanged.

After Owner approval, run the existing scheduler script from the approved
Windows checkout; it registers/updates **all six tasks**, not just reminders.
The task account needs Python/dependencies, checkout access and the existing
approved agent environment. `run-agent.ps1` sets the package working directory
and restores the previous directory and `PYTHONPATH` even on failure.
Verify the resulting Task Scheduler XML, daily trigger/repetition, task
principal/logon mode, missed-run policy and next-day execution. The script
does not configure unattended credentials or `StartWhenAvailable`.

Secrets must come from the approved secret manager/environment or existing
git-ignored `.env` read by `apps.agents.config`. Never put them in task
arguments, screenshots, source or logs. Masked inventory example only:

```dotenv
AGENTS_SECRET=<masked; must match API AGENTS_SECRET>
AGENTS_API_BASE=<approved API URL; not a secret>
AGENTS_API_TIMEOUT_SECONDS=120
TELEGRAM_BOT_TOKEN=<masked; API-side delivery only>
TELEGRAM_OWNER_CHAT_ID=<masked; API-side delivery only>
```

## Linux Scheduler Template (Not Installed or Executed)

Use the **existing VPS Linux scheduler**, in the **existing `/opt/icebeach`
checkout**, after Owner GO. The command runs the CLI inside the existing
`api` service, where `AGENTS_SECRET` is already injected from `.env.docker`.
It overrides only `AGENTS_API_BASE` to the container's own loopback API on
the existing port 8000. No secret is embedded in the command, and no new
service/container/Compose project is created.

Prerequisites: confirm `/opt/icebeach` resolves to the approved checkout,
verify Compose project identity and `api` service, deployed SHA, container
module availability, existing protected `/var/lib/ruza` and `/var/log/ruza`,
and installed absolute paths to `docker`, `flock` and `sh`. Use the existing
scheduler principal; Docker access is privileged and must not be newly
granted just for this feature. Lock/log files must be writable only by the
approved principal. Resolve deployment symlinks before collecting evidence.

**Template only**, an entry to review for the existing scheduler (not an
instruction to replace `crontab` or execute it in this QA task):

```cron
* * * * * /bin/sh -c 'cd /opt/icebeach && /usr/bin/flock -n -E 75 /var/lib/ruza/shift-reminders.lock /usr/bin/docker compose --env-file .env.docker exec -T --workdir /app -e AGENTS_API_BASE=http://127.0.0.1:8000 api python -m apps.agents.cli run --agent shift_reminders; rc=$?; echo "shift_reminders exit=$rc"; exit "$rc"' >> /var/log/ruza/shift-reminders.cron.out 2>&1
```

The one-minute, all-day cadence avoids a host-timezone/shift-hour blind spot.
`flock` prevents overlapping invocations using this shared lock; exit 75 means
lock contention, not successful delivery. A different lock, another host,
manual CLI call or a Windows task bypasses this protection: activate exactly
one scheduler owner and disable duplicates. Do not run the Windows schedule
and Linux schedule simultaneously. Docker/runtime/HTTP failures are nonzero;
exit 0 means the API call succeeded, NOT proof of Telegram delivery.
Repeated failures/lock skips, run duration, request volume and log retention
need monitoring using the existing operations process. Do not add per-minute
Telegram success messages or use automatic retries after an ambiguous timeout
until delivery idempotency is proven.

## Production Proof Criteria (EXTERNAL / Not Proven by Local Tests)

1. Owner GO and approved placement/principal; pinned deployed Git SHA and
   clean release-tree evidence; verify the API container contains the same
   CLI/runner revision. Preserve rollback evidence and existing schedules.
2. Validate existing production env without exposing values; agent/API secret
   agreement, API health, Sheets permissions, club timezone and reminder
   columns (`admin_notice_15_sent_at`, `admin_notice_5_sent_at`,
   `client_notice_15_sent_at`, `client_notice_5_sent_at`). Delivery tokens
   remain API-side. The CLI alone cannot prove schema or delivery readiness.
3. First prove on isolated staging/test records: T-15 and T-5 windows, local
   date boundary, confirmed/late eligibility, terminal-state exclusions,
   no-target/missing-channel behavior, delivery failure followed by retry,
   repeated invocation without duplicate deliveries, and concurrent launch.
   Failed delivery must not become a false sent marker. Resolve timer/delivery
   findings with their owners; this integration does not change those services.
4. Show installed scheduler definition, working directory/project identity,
   single owner/lock, redacted output and captured process exit status. Prove
   execution after midnight, through the next day and after an approved
   restart/missed-run scenario. API errors must surface as failed runs.
5. Only after separate explicit send/write authorization, collect approved
   live reminder receipt plus matching audit/booking marker, then a repeated
   run with no duplicate. CLI counters, HTTP 200, green CI and scheduler
   installation alone are insufficient production proof.

## Risks and Rollback

At one request per minute, idle load is roughly 1,440 calls/day; measure Sheets
reads/cache/quota and longest execution before activation. Scheduler locks
are not distributed idempotency. A three-minute Windows kill or an API timeout
can leave ambiguous delivery state; inspect the audit before retrying.
Counter output may contain operational identifiers: keep scheduler logs
protected, redacted in evidence, and managed by existing retention policy.

Existing finding outside this logical change: `late_marker` still uses the
legacy `Once` trigger with a 14-hour repetition duration. It does not renew
on subsequent days. Its schedule is intentionally unchanged and needs a
separate operations fix/proof before relying on unattended late marking.

Rollback requires Owner approval in a live environment. Disable only
`IceBeach-Agent-ShiftReminders` on Windows, or remove/disable only its Linux
scheduler entry after saving the previous definition. Do NOT stop the API,
Telegram bot, existing monitor or other agents. The existing
`schedule-agents.ps1 -Unregister` removes all six agent tasks and is broader
than a reminder-only rollback. Revert only this integration after stopping
its schedule; no database/schema rollback is required. Already sent messages
and persisted API side effects are not undone by removing the schedule.

Next gate: merge independent delivery/timer fixes and collect the EXTERNAL
proof above; scheduling is not activated by this code change.
