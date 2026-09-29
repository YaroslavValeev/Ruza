# Intake Sync: сайт и Telegram → RuzaTab

## Канон

1. Сайт `mywavewake.ru` и Telegram-бот записывают заявки в каноническую таблицу
   MyWave, вкладку `Ruza`.
2. `intake_sync` переносит новые заявки в `RuzaTab.leads`.
3. Оператор связывается со спортсменом, проверяет слот и цену и только затем
   создаёт `booking`.

Автоматическое создание брони из внешней заявки запрещено: оно может привести
к overbook или фиксации неверной цены.

## Идемпотентность

- Канонический ключ: `external_source + external_record_id`.
- `external_record_id` равен `request_id` исходной строки.
- `lead_id` детерминирован, поэтому повторный запуск безопасен даже после
  сетевого сбоя.
- `received_at`, `sync_status`, `sync_error`, `converted_booking_id` фиксируют
  состояние переноса в операционную таблицу.

## Переменные

```dotenv
SPREADSHEET_ID=<RuzaTab ID>
INTAKE_SPREADSHEET_ID=<canonical MyWave spreadsheet ID>
INTAKE_TAB_NAME=Ruza
AGENTS_SECRET=<long random secret>
```

## Запуск

Локально или вручную на сервере:

```powershell
.\scripts\run-agent.ps1 -Agent intake_sync
```

Live/local proof без дублей:

```powershell
.\scripts\intake-e2e-local.ps1
```

Что делает проверка:

- добавляет одну тестовую строку в каноническую intake-таблицу, если её ещё нет;
- запускает `sync_intake_leads`;
- запускает sync повторно;
- проверяет, что в `RuzaTab.leads` существует ровно один lead с тем же
  `external_record_id`;
- завершает работу только при `SUMMARY failures=0`.

По умолчанию используется детерминированный `request_id` вида
`smoke-intake-e2e-YYYYMMDD`, поэтому повторный запуск в тот же день не создаёт
дубликаты.

Через API планировщика:

```text
POST /internal/agents/intake-sync
X-Agents-Secret: <AGENTS_SECRET>
```

Production-интервал: каждые 5 минут. Успешный пустой запуск возвращает
`scanned=0`, `created=0`, `errors=[]`.

## Карта полей

| Canonical `Ruza` | `RuzaTab.leads` |
|---|---|
| `request_id` | `external_record_id` |
| `parent_name` / `child_name` | `full_name` |
| `phone` | `phone` (только цифры) |
| `source_cta` | `source` |
| `utm_source` | `utm_source` |
| `utm_campaign` | `utm_campaign` |
| `created_at` | `created_at`, `received_at` |
| sync result | `sync_status`, `sync_error`, `converted_booking_id` |
| operational context | `notes` |

## Rollback

Остановить расписание `intake_sync`. Уже созданные лиды не удалять: они имеют
`external_record_id`, поэтому могут быть сверены с источником вручную.
