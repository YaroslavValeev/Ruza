# Ruza production v1 gates

Этот файл фиксирует проверяемые ворота перед production v1. Он не заменяет CI и release tag.

## 1. Source code / release

PASS только если:
- `git status --porcelain` пустой;
- backend tests проходят;
- dashboard build проходит;
- release tag указывает на тот же SHA, который прошел CI;
- production deploy запускается только через guard `scripts/server/assert-clean-release-tree.sh`.

Локальная проверка:

```powershell
git status --short
cd .\icebeach-wakeclub
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q
cd .\apps\dashboard
npm run build
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

Повторная доставка одной внешней заявки проверяется тестом `test_contract_intake.py`.

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

PASS только если платежи и возвраты проходят `test_contract_payments.py`.

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
