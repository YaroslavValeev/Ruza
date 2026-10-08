# Ruza production v1 gates

Этот файл фиксирует проверяемые ворота перед production v1. Он не заменяет CI и release tag.

Актуализация: **2026-10-07 MSK** — добавлены EXTERNAL evidence 2026-10-06/07 (см. §8);
база кода: main `d909083` (после PR #7).
Turism — вне scope. Ротация секретов — только Owner вручную. Deploy/merge на main — только Owner GO.

## 1. Source code / release

PASS только если:
- `git status --porcelain` пустой;
- backend tests проходят;
- dashboard build проходит;
- dashboard dependency audit проходит без low-or-higher findings на **production deps**:
  `npm audit --omit=dev --audit-level=low` (как в `.github/workflows/ci.yml`);
- release tag указывает на тот же SHA, который прошел CI
  (текущий tip main: `bd77c197`; tag `v1.0.0-rc.19` → `51180f3` **отстаёт** от main);
- production deploy запускается только через clean-tree guard:
  `scripts/server/assert-clean-release-tree.ps1` на Windows/local и
  `scripts/server/assert-clean-release-tree.sh` на Linux/VPS;
- CI проверяет, что clean-tree guard принимает чистый release checkout и блокирует
  dirty working tree на Linux и Windows;
- CI проверяет dashboard dependency audit через `npm audit --omit=dev --audit-level=low`;
- CI проверяет поведение staging/prod proof-gate для HTTPS, dashboard, health,
  CORS credentials, authenticated preflight и OTP debug leakage без внешних side effects;
- CI проверяет server healthcheck для monitoring/alerting без внешних side effects;
- CI проверяет restore backup dry-run/hash/write guard без внешних side effects;
- CI проверяет rollback guard без внешних side effects;
- CI проверяет mobile/PWA readiness без внешних side effects: iOS meta, manifest,
  service worker, safe-area, mobile routes, same-origin `/api` и отсутствие видимых
  слов `Игрок/игровой` в dashboard copy;
- production env проходит machine-check:
  `scripts/validate-production-env.ps1` на Windows/local и
  `scripts/server/validate-production-env.sh` на Linux/VPS;
- CI проверяет, что env guard принимает production-like env и блокирует debug/local env
  на Linux и Windows.

Локальная проверка:

```powershell
git status --short
cd .\icebeach-wakeclub
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q
cd .\apps\dashboard
npm run build
npm audit --omit=dev --audit-level=low
powershell -ExecutionPolicy Bypass -File ..\..\..\scripts\server\assert-clean-release-tree.ps1
```

Единый локальный release audit перед staging:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\production-v1-local-audit.ps1
```

Скрипт проверяет clean tree, PR SHA, CI, remote tag, evidence docs, backend tests, dashboard build и dashboard dependency audit.
Внешние ворота (`HTTPS`, real OTP proof, live intake, restore-write, monitoring, iOS Safari, real shift)
выводятся как `EXTERNAL` и не должны трактоваться как закрытые локально.

Staging/prod proof после публикации URL:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\staging-proof.ps1 `
  -ApiBaseUrl "https://<api-domain>" `
  -DashboardUrl "https://<dashboard-domain>" `
  -Date "2026-06-01"
```

Локальная проверка поведения proof-gate без реальных внешних сервисов:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-staging-proof.ps1
bash scripts/server/test-staging-proof.sh
```

Server healthcheck / alerting guard без реальных внешних сервисов:

```powershell
bash scripts/server/test-healthcheck.sh
```

Production env перед staging/deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-production-env.ps1 -EnvFile .\.env.docker
```

На Linux/VPS тот же gate выполняется автоматически внутри `scripts/server/deploy-api.sh`
и должен выполняться перед `docker compose` на `/opt/icebeach`.

Проверка поведения guard без секретов:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-production-env-guards.ps1
bash scripts/server/test-production-env-guards.sh
powershell -ExecutionPolicy Bypass -File .\scripts\test-clean-release-tree.ps1
bash scripts/server/test-clean-release-tree.sh
```

## 2. Sheets schema / intake

PASS только если `preflight-local.ps1` показывает `blockers=0`.

Production API не должен стартовать без:
- `INTAKE_SPREADSHEET_ID` — каноническая таблица заявок сайта/TG;
- `AGENTS_SECRET` — секрет для scheduled/internal agents.

Обязательные intake поля в `leads`:
- `external_source`
- `external_record_id`
- `received_at`
- `sync_status`
- `sync_error`
- `converted_booking_id`

Повторная доставка одной внешней заявки проверяется:
- контрактом `test_contract_intake.py`;
- live/local proof-командой:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\intake-e2e-local.ps1
```

PASS только если команда завершилась строкой `SUMMARY failures=0` и показала
ровно один lead в `RuzaTab.leads` для выбранного `external_record_id`.

## 3. Auth / OTP (production path)

Canonical order in `otp_delivery.py`:
1. Phone HTTPS webhook (`OTP_DELIVERY_WEBHOOK_URL` + token), if configured;
2. Else Telegram bot (`TELEGRAM_BOT_TOKEN`) to staff `telegram_id`;
3. Else manual — **local/test only** (`ALLOW_MANUAL_OTP_DELIVERY` must be `false` in production).

Production config / env guards (post PR #7):
- `ALLOW_MANUAL_OTP_DELIVERY=false` always in production;
- **either** a real HTTPS SMS webhook + token, **or** `TELEGRAM_BOT_TOKEN` set;
- SMS webhook may be empty when Telegram bot token is present;
- debug OTP / legacy staff login remain forbidden in production.

PASS production OTP only after EXTERNAL proof that a real staff login receives a code
via Telegram (or SMS webhook) under HTTPS cookies — not merely that env validates.

## 4. Payment ledger

KPI production v1 считает поступления из `payments`, а не только `bookings.total_price`.

Owner decision: платежи в Ruza остаются ручным ledger в Google Sheets.
В scope v1 не входят card acquiring, внешний payment provider, provider webhooks
и lifecycle статусов от провайдера. Поля `provider` и `external_payment_id`
сохраняются как audit/metadata-only.

Обязательные поля:
- `booking_id`
- `kind`
- `status`
- `method`
- `amount_minor`
- `paid_at`
- `parent_payment_id`
- `idempotency_key`

PASS только если платежи и возвраты проходят `test_contract_payments.py`, включая
`test_payment_rbac_and_kpi_real_money`: неоплаченная завершённая бронь может
увеличивать количество сессий и стоимость завершённых заездов, но не должна
увеличивать `payments_gross_minor` и `net_revenue_minor` в KPI.

## 5. Backup / restore

Перед staging/prod:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-sheets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\restore-sheets-backup.ps1 -BackupDir .\backups\sheets\<timestamp>
```

`restore-sheets-backup.ps1` без `-Write` выполняет dry-run и проверяет integrity hash.
Запись в тестовую таблицу выполняется только с явным `-Write -TargetSpreadsheetId <id>`.

Guard на запись (`scripts/restore_sheets_backup.py --write`):
- пустой `--target-spreadsheet-id` → отказ (`RESTORE_REFUSED`, exit code 2);
- target равен `SPREADSHEET_ID` или `INTAKE_SPREADSHEET_ID` (env + app settings, включая
  repo `.env`, который грузит `apps.api.app.config`) → отказ, exit code 2, без обращений к Google;
- если app settings не загружаются (нет зависимостей API / `PYTHONPATH`) → отказ (fail-closed);
- disaster recovery в prod-таблицу — только явным `--allow-prod-target`
  (`-AllowProdTarget` в `.ps1`) **и** вводом фразы `OVERWRITE SPREADSHEET_ID`
  (или `OVERWRITE INTAKE_SPREADSHEET_ID`) в интерактивном терминале; без TTY — отказ.
  Использовать только с Owner GO и после свежего `backup-sheets.ps1`.

Проверка поведения restore guard без Google Sheets:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-restore-sheets-backup.ps1
python scripts/test_restore_sheets_backup.py
```

Guard на prod-target покрыт pytest:
`icebeach-wakeclub/apps/api/tests/test_restore_sheets_backup_guard.py` (входит в backend tests).

## 6. Mobile / PWA / iOS readiness

Локально и в CI проверяются предпосылки для Android/iOS PWA:
- `viewport-fit=cover`, Apple PWA meta, manifest и touch icon;
- manifest `standalone`, portrait, `/m/pilot` и shortcuts `/m/pilot`, `/m/owner`;
- service worker и мобильные routes `/m/pilot`, `/m/owner`, `/m/install`;
- safe-area insets и 48px touch targets в mobile shell;
- production dashboard build использует same-origin `/api`, а nginx dashboard
  проксирует `/api/` в API service;
- пользовательский dashboard copy не возвращает `Игрок/игровой`.

Проверка:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test-mobile-readiness.ps1
python scripts/mobile_readiness.py
```

Это не заменяет реальный iOS Safari smoke по HTTPS. PASS production v1 только
после ручного прохода основного сценария на iPhone/iPad с HTTPS staging/prod URL.

## 7. Staging / production gates (VPS docker compose)

Primary production-like path: **VPS + docker compose** at `/opt/icebeach`
(containers `icebeach-api-1`, `icebeach-dashboard-1`). Timeweb App Platform remains
an optional alternative documented in `SERVER_COMMANDS.md`.

Checkout for updates should track **`origin/main` or a new annotated tag** that
points at the intended SHA — not only historical `v1.0.0-rc.19`.

Monitoring healthcheck после deploy:

```bash
bash scripts/server/healthcheck.sh \
  --api-url "https://<api-domain>" \
  --dashboard-url "https://<dashboard-domain>" \
  --log-file "/var/log/ruza/healthcheck.log"
```

С webhook-алертом:

```bash
bash scripts/server/healthcheck.sh \
  --api-url "https://<api-domain>" \
  --dashboard-url "https://<dashboard-domain>" \
  --log-file "/var/log/ruza/healthcheck.log" \
  --alert-webhook-url "https://<alert-webhook>"
```

Rollback dry-run:

```bash
bash scripts/server/rollback-api.sh --target-tag "v1.0.0-rc.<previous>"
```

Rollback execute на staging/prod выполняется только с явным `--execute`:

```bash
bash scripts/server/rollback-api.sh \
  --target-tag "v1.0.0-rc.<previous>" \
  --healthcheck-command "bash scripts/server/healthcheck.sh --api-url https://<api-domain> --dashboard-url https://<dashboard-domain>" \
  --execute
```

Пока не считать v1 / Cash-cow 10/10 завершённым без EXTERNAL (статус на 2026-10-07 MSK, детали в §8):
- staging/production HTTPS — **PASS** 2026-10-06;
- green `scripts/staging-proof.ps1` на staging/prod URL — **PASS** (`blockers=0`);
- production OTP proof (Telegram bot token path **or** HTTPS SMS webhook) — **PASS** (Telegram);
- backup restore-test на отдельной таблице — **PASS** 2026-10-07;
- monitoring + alerting — **PASS (internal cron + Telegram)**; внешний uptime monitor — **OPEN**;
- rollback drill — dry-run **PASS**; `--execute` — **OPEN** (только с Owner GO);
- Android и iOS Safari smoke — **OPEN**;
- live intake без дублей — **OPEN**;
- одна реальная смена без P0 (сначала dry-run смены) — **OPEN**;
- Owner GO на tag/deploy (агенты не деплоят).

## 8. EXTERNAL evidence 2026-10-06/07 (MSK)

Все времена — MSK (UTC+3). Секреты, токены и id таблиц в этот файл не вносятся.

| Gate | Статус | Evidence |
|---|---|---|
| HTTPS | PASS | `https://ruza.mywavewake.ru` через nginx + Let's Encrypt (certbot). Сертификат действует до **2027-01-04**, auto-renew (certbot). |
| Production OTP | PASS | Live Telegram OTP на prod: `request-code` → `delivery_channel=telegram`, `debug_code=null`; `verify-code` OK; `/auth/me` OK под HTTPS-cookie. |
| Monitoring + alerting | PASS (internal) | `/usr/local/bin/ruza-healthcheck-alert.sh` по cron каждые 5 минут; обёртка над `scripts/server/healthcheck.sh`; Telegram DM через Ruza bot **только при смене состояния**; состояние в `/var/lib/ruza/health.state`. Тестовый прогон `rc=0`, recovery-сообщение получено. Скрипт: `SERVER_COMMANDS.md` → «Telegram alert на смену состояния». |
| Rollback drill | PARTIAL | Dry-run `rollback-api.sh --target-tag v1.0.0-rc.19` → `ROLLBACK_PLAN_OK target=v1.0.0-rc.19`. `--execute` **не запускался** (только с Owner GO). |
| Staging/prod proof | PASS | `scripts/staging-proof.ps1` с Windows против prod URL → `SUMMARY blockers=0`. Примечания: Xray VPN давал TLS timeouts (запускать без VPN/в обход); `curl` на Windows (schannel) требует `--ssl-no-revoke`. |
| Sheets schema migration | PASS | Перед миграцией backup `20261007T144730Z` (UTC; 17:47 MSK). Добавлены 12 колонок в `bookings` и `clients.telegram_id` (append справа, существующие колонки не двигались). Preflight на дату `2026-09-30` → `blockers=0`. Даты вне сезона дают blocker availability **by design**: сезон захардкожен `06-01..10-01` (`operating_calendar.py`); работа над настраиваемым сезоном поставлена Owner на паузу. |
| Backup restore-write | PASS | Backup восстановлен (`--write`) в **отдельную тестовую таблицу** (не prod); все 15 вкладок совпали по количеству строк и значениям; dry-run integrity hash check OK. С этого PR `--write` в `SPREADSHEET_ID`/`INTAKE_SPREADSHEET_ID` блокируется guard'ом (§5). |

Осталось (OPEN):
- iOS Safari и Android smoke основного сценария по HTTPS;
- live intake (сайт/TG) без дублей лидов;
- реальный dry-run смены, затем реальная смена без P0;
- rollback `--execute` — только с Owner GO;
- внешний uptime monitor (независимо от VPS cron).
