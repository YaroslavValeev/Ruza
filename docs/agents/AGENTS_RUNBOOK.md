# Runbook операционных Agents

## Запуск вручную

**[PowerShell]**

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\run-agent.ps1 -Agent preflight_guard
.\scripts\run-agent.ps1 -Agent late_marker
.\scripts\run-agent.ps1 -Agent shift_snapshot
.\scripts\run-agent.ps1 -Agent ops_alert
.\scripts\run-agent.ps1 -Agent daily_brief -Mode morning
.\scripts\run-agent.ps1 -Agent daily_brief -Mode evening
.\scripts\run-agent.ps1 -Agent intake_sync
```

## Проверка

```powershell
.\scripts\agents-smoke.ps1
Get-Content logs\agents.log -Tail 30
```

## Переменные (.env)

| Переменная | Назначение |
|------------|------------|
| `AGENTS_SECRET` | заголовок `X-Agents-Secret` для internal API |
| `AGENTS_API_BASE` | URL API (default `http://127.0.0.1:8000`) |
| `TELEGRAM_BOT_TOKEN` | optional |
| `TELEGRAM_OWNER_CHAT_ID` | optional |
| `PUBLIC_CLUB_ID` | клуб для `/public/*` |
| `INTAKE_SPREADSHEET_ID` | каноническая таблица входящих заявок |
| `INTAKE_TAB_NAME` | вкладка источника, по умолчанию `Ruza` |

## Агенты

### PreflightGuard
- Вызывает `GET /internal/agents/preflight`
- При blockers > 0 → OpsAlert

### LateMarker
- `POST /internal/agents/mark-late?minutes_before=10`
- Только в часы смены (скрипт проверяет 08–22)

### ShiftSnapshot
- `POST /internal/agents/snapshot` за сегодня

### OpsAlert
- health + preflight; пишет в `logs/agents.log` или Telegram

### DailyBrief
- `GET /internal/agents/daily-brief?mode=morning|evening`

### QueueCoach
- UI-only: карточка «Следующий заезд» на `/m/pilot` и `/pilot`

### IntakeSync
- `POST /internal/agents/intake-sync`
- Переносит новые строки `Ruza` в операционную вкладку `leads`
- Повторный запуск безопасен: `external_source + external_record_id` не дублируются
- Рекомендуемый production-интервал: каждые 5 минут

## Rollback

Отключить Task Scheduler:

```powershell
.\scripts\schedule-agents.ps1 -Unregister
```
