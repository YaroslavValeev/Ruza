# Ruza production v1 gates

Этот файл фиксирует проверяемые ворота перед production v1. Он не заменяет CI и release tag.

## 1. Source code / release

PASS только если:
- `git status --porcelain` пустой;
- backend tests проходят;
- dashboard build проходит;
- dashboard dependency audit проходит без low-or-higher findings;
- release tag указывает на тот же SHA, который прошел CI;
- production deploy запускается только через clean-tree guard:
  `scripts/server/assert-clean-release-tree.ps1` на Windows/local и
  `scripts/server/assert-clean-release-tree.sh` на Linux/Timeweb;
- CI проверяет, что clean-tree guard принимает чистый release checkout и блокирует
  dirty working tree на Linux и Windows;
- CI проверяет dashboard dependency audit через `npm audit --audit-level=low`;
- production env проходит machine-check:
  `scripts/validate-production-env.ps1` на Windows/local и
  `scripts/server/validate-production-env.sh` на Linux/Timeweb;
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
npm audit --audit-level=low
powershell -ExecutionPolicy Bypass -File ..\..\..\scripts\server\assert-clean-release-tree.ps1
```

Единый локальный release audit перед staging:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\production-v1-local-audit.ps1
```

Скрипт проверяет clean tree, PR SHA, CI, remote tag, evidence docs, backend tests, dashboard build и dashboard dependency audit.
Внешние ворота (`Timeweb`, real OTP, live intake, restore-write, monitoring, iOS Safari, real shift)
выводятся как `EXTERNAL` и не должны трактоваться как закрытые локально.

Production env перед staging/deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-production-env.ps1 -EnvFile .\.env.docker
```

На Linux/Timeweb тот же gate выполняется автоматически внутри `scripts/server/deploy-api.sh`.

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

## 3. Payment ledger

KPI production v1 считает поступления из `payments`, а не только `bookings.total_price`.

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

## 4. Backup / restore

Перед staging/prod:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-sheets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\restore-sheets-backup.ps1 -BackupDir .\backups\sheets\<timestamp>
```

`restore-sheets-backup.ps1` без `-Write` выполняет dry-run и проверяет integrity hash.
Запись в тестовую таблицу выполняется только с явным `-Write -TargetSpreadsheetId <id>`.

## 5. Staging / production gates

Пока не считать v1 завершенным без:
- staging HTTPS;
- production HTTPS;
- production-ready OTP webhook;
- backup restore-test на отдельной таблице;
- monitoring + alerting;
- rollback drill;
- Android и iOS Safari smoke;
- одна реальная смена без P0.
