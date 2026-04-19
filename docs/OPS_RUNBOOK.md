# OPS Runbook (Windows, 5–10 минут)

## 1) Подготовка

1. Скопировать `.env.example` -> `.env`.
2. Положить service account JSON в `secrets/service-account.json`.
3. Убедиться, что сервис-аккаунт имеет Editor-доступ к Google Sheet.

## 2) API

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic
uvicorn apps.api.app.main:app --reload --port 8000
```

Проверка:

```powershell
curl http://localhost:8000/health
```

## 3) Dashboard

```powershell
cd apps/dashboard
npm install
npm run dev
```

## 4) Hooks

```powershell
git config core.hooksPath .githooks
```

## 5) First login smoke

1. Войти под admin через phone из `staff_users`.
2. Открыть `/operator`, `/pilot`, `/kpi`.
3. Проверить `/ops/diagnostics`.

## 6) Ссылки на чеклисты

- `docs/WEEK5_LAUNCH_CHECKLIST.md`
- `docs/TROUBLESHOOTING.md`
- `docs/PILOT_RUN_DAY1.md`
