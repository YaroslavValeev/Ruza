# 23. Staging Launch Checklist

## Перед деплоем
- GitHub репозиторий актуален
- `SPREADSHEET_ID` проверен
- service account имеет доступ к spreadsheet
- `SESSION_SECRET` сгенерирован заново под staging
- staging domain для dashboard определён
- `CORS_ALLOW_ORIGINS` заполнен точным доменом

## После деплоя backend
- `/health` отвечает `200`
- `/preflight/summary?date=2026-06-01` отвечает без blockers
- `/smoke/run?date=2026-06-10` отвечает `ok=true`

## После подключения frontend
- login по коду работает
- KPI открывается
- Брони открываются
- Pilot открывается
- `ride_type`, `wetsuit_gender`, `wetsuit_size` сохраняются

## NO-GO для staging demo
- `health` красный
- `preflight` даёт blockers
- `smoke` даёт failures
- браузер получает CORS error
- cookies не ставятся

## GO для перехода к mobile-first frontend
- backend staging зелёный
- smoke стабильно зелёный минимум 2 запуска подряд
- ручной цикл `booking -> ready -> in_progress -> done` проходит на staging
