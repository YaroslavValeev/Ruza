# Ruza release plan (living)

Last updated: **2026-10-07 MSK**  
Source of truth for status: [`PRODUCTION_V1_AUDIT.md`](PRODUCTION_V1_AUDIT.md), gates: [`PRODUCTION_V1_GATES.md`](PRODUCTION_V1_GATES.md), VPS commands: [`SERVER_COMMANDS.md`](SERVER_COMMANDS.md).

## Policy (non-negotiable for agents)

- **Do not** merge to `main` without Owner.
- **Do not** deploy production / VPS without Owner GO.
- **Do not** rotate secrets from agent sessions.
- **Turism** is out of scope for Ruza Cash-cow.
- Prefer honest **EXTERNAL** labels over fake green.

## Current baseline (verified)

| Item | Value |
|---|---|
| `origin/main` tip | `bd77c197` — Merge PR #7 (2026-10-05) |
| PR #7 contents | access limits, rate-limit, timezone, admin ride timer, Telegram OTP for production, CI `npm audit --omit=dev` |
| Production VPS | `root@4169037-ep26382`, `/opt/icebeach`, docker compose (`icebeach-api-1`, `icebeach-dashboard-1`), detached clean at `bd77c197` |
| Telegram OTP | Allowed in production when `TELEGRAM_BOT_TOKEN` set; SMS webhook may be empty |
| Tag `v1.0.0-rc.19` | Points at `51180f3` (**behind** main) |
| Stale PR #1 | Closed `not_planned` by AGM |
| Public URL | `https://ruza.mywavewake.ru` — nginx + Let's Encrypt, cert до 2027-01-04, auto-renew (2026-10-06) |
| Restore guard | `restore_sheets_backup.py --write` refuses empty target and `SPREADSHEET_ID` / `INTAKE_SPREADSHEET_ID` (override `--allow-prod-target` + typed confirmation) |

## Done (Cash-cow core on main)

1. Booking → check-in → pilot → done FSM with contract tests.
2. RBAC sessions from `staff_users`; production blocks debug OTP / legacy login / manual OTP.
3. Phone rate-limit + access limits (PR #7).
4. Timezone / local shift date handling (PR #7).
5. Admin ride timer (PR #7).
6. Payment ledger + KPI net revenue from `payments` (manual Sheets; no acquiring provider).
7. Intake sync path into `leads` (idempotent) — live writers still EXTERNAL.
8. CI gates: api tests, dashboard build, `npm audit --omit=dev --audit-level=low`, env/clean-tree/staging-proof/healthcheck/restore/rollback/mobile guards.
9. VPS compose path documented and in use at `/opt/icebeach`.

## Next: ordered backlog to Cash-cow 10/10

Execute in order unless Owner reprioritizes. Items marked **EXTERNAL** need Owner/operator on real infra.

1. **Docs/plan alignment (this PR)** — audit/gates/server/quality/README + this living plan; no deploy.
2. **Optional tag `v1.0.0-rc.20`** on `bd77c197` — Owner only:
   ```powershell
   git fetch origin
   git tag -a v1.0.0-rc.20 bd77c197 -m "Ruza RC20: main after PR #7 (access, OTP telegram, CI omit=dev)"
   $env:ALLOW_GIT_PUSH=1; git push origin v1.0.0-rc.20
   ```
3. ✅ **EXTERNAL — HTTPS proof** — DONE 2026-10-06/07: `https://ruza.mywavewake.ru` (nginx + Let's Encrypt, cert до 2027-01-04, auto-renew); `scripts/staging-proof.ps1` с Windows → `blockers=0` (без Xray VPN; `curl --ssl-no-revoke` на Windows schannel).
4. ✅ **EXTERNAL — OTP proof** — DONE: live Telegram OTP на prod, `delivery_channel=telegram`, `debug_code=null`, `verify-code` и `/auth/me` OK.
5. ✅ **EXTERNAL — monitoring** — DONE (internal): `/usr/local/bin/ruza-healthcheck-alert.sh` по cron каждые 5 мин, Telegram DM через Ruza bot только при смене состояния (`/var/lib/ruza/health.state`); тест `rc=0`, recovery-сообщение получено. **Open:** внешний uptime monitor.
6. ✅ **EXTERNAL — backup restore-write** — DONE 2026-10-07: backup восстановлен в отдельную тестовую таблицу, 15/15 вкладок совпали (строки и значения); dry-run hash OK. Перед этим Sheets migration: backup `20261007T144730Z`, +12 колонок `bookings`, +`clients.telegram_id`; preflight `2026-09-30` → `blockers=0`.
7. ◐ **EXTERNAL — rollback drill** — dry-run DONE (`ROLLBACK_PLAN_OK target=v1.0.0-rc.19`); `--execute` **только с Owner GO** (не запускался).
8. **EXTERNAL — intake live** — site/TG writers + scheduler; prove no duplicate leads.
9. **EXTERNAL — mobile** — Android + **iOS Safari** main scenario on HTTPS.
10. **EXTERNAL — dry-run shift then real shift** — SOP; no P0.

Known by design: даты вне сезона (`06-01..10-01`, захардкожено в `operating_calendar.py`) дают blocker availability в preflight; настраиваемый сезон — на паузе по решению Owner.

Definition of Cash-cow **10/10**: items 3–10 green with evidence links in audit; Owner signs GO.

## After Cash-cow 10/10 (next slices, still not Turism)

Ordered product slices only after 10/10 or explicit Owner override:

1. UX polish for shift board (operator speed, fewer taps) without breaking FSM.
2. Stronger Sheets concurrency / single-writer discipline documentation + any safe retries.
3. Frontend unit/a11y smoke where it protects Cash-cow paths.
4. Marketing funnel hardening (lead status SOP) — no CAC provider work unless Owner asks.
5. Voice/edge prototypes remain non-blocking; do not gate Cash-cow.

Explicitly **later / other repos**: SponsorOS, Gear, Personal_Helper merge, Turism.

## Optional Owner commands (not run by this docs PR)

Tag RC20 (see backlog #2).  
VPS update after Owner GO (see `SERVER_COMMANDS.md` §4): fetch, checkout `origin/main` or new tag, clean-tree + env validate, `docker compose up --build -d`.

## Change log

| Date | Change |
|---|---|
| 2026-10-05 | Initial living plan after PR #7 merge; EXTERNAL gates listed honestly; tag rc.19 lag noted |
| 2026-10-07 | EXTERNAL evidence 2026-10-06/07: HTTPS, Telegram OTP, healthcheck alerting, rollback dry-run, staging-proof, Sheets migration, restore-write into test sheet; restore `--write` prod-target guard |
