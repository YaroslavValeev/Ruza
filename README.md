# Ruza — Ice Beach Wake Club Automation

Цифровая экосистема клуба «Айс пляж» (Руза): каноническая таблица MyWave для
входящих заявок, операционная RuzaTab для смены, FastAPI backend и React dashboard.

## Стек

- **Backend:** Python 3.11, FastAPI, Google Sheets API
- **Frontend:** React 18, Vite 5, Tailwind CSS
- **Auth:** RBAC по `staff_users` в Sheets, cookie session + SMS-код
- **Deploy:** Docker → Timeweb App Platform (staging)

## Source of Truth

- Входящие заявки сайта `mywavewake.ru` и Telegram: каноническая таблица MyWave,
  вкладка `Ruza` (`INTAKE_SPREADSHEET_ID`).
- Операции клуба: RuzaTab (`SPREADSHEET_ID`), включая `clients`, `leads`,
  `bookings`, `checkins`, `audit_log` и KPI.
- `intake_sync` переносит заявку в `leads` идемпотентно. Бронь создаёт оператор
  только после проверки слота и цены.

## Быстрый старт (локально)

**[PowerShell]**

```powershell
cd "f:\Проекты MyWave\NEW2026\Ruza"

# 1. Секреты (не коммитить)
Copy-Item icebeach-wakeclub\apps\api\.env.example icebeach-wakeclub\apps\api\.env
# Заполнить SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON, SESSION_SECRET

# 2. Backend deps
pip install -r icebeach-wakeclub\apps\api\requirements.txt

# 3. Frontend deps
cd icebeach-wakeclub\apps\dashboard
npm install
cd ..\..\..

# 4. Запуск
.\scripts\install-hooks.ps1
.\scripts\start-local.ps1
.\scripts\status-local.ps1
```

Если `8000` занят другим локальным проектом, используйте тот же dashboard `5173`,
но поднимите Ruza API на свободном порту:

```powershell
.\scripts\stop-local.ps1 -ApiPort 8000
.\scripts\start-local.ps1 -Lan -ApiPort 8001
.\scripts\status-local.ps1 -ApiPort 8001
.\scripts\preflight-local.ps1 -Date "2026-06-01" -ApiPort 8001
.\scripts\smoke-local.ps1 -Date "2026-06-01" -ApiPort 8001
```

## Локальный demo без Google Sheets

**[PowerShell]**
```powershell
pip install -r icebeach-wakeclub\apps\api\requirements.txt
.\scripts\start-demo.ps1
$env:PYTHONPATH=(Resolve-Path .\icebeach-wakeclub).Path
python scripts\smoke_demo.py
```

**[WSL2]**
```bash
pip install -r icebeach-wakeclub/apps/api/requirements.txt
chmod +x scripts/start-demo.sh scripts/check.sh
./scripts/start-demo.sh
```

В другом терминале:
```bash
PYTHONPATH="$PWD/icebeach-wakeclub" python3 scripts/smoke_demo.py
```

Открыть http://127.0.0.1:5173 — кнопки Админ / Оператор / Пилот, затем «Получить код». DEV-код на форме.

- API: http://127.0.0.1:8000/health или fallback http://127.0.0.1:8001/health
- Стоп Windows: `.\scripts\stop-local.ps1`

## Docker

**[PowerShell]**

```powershell
Copy-Item .env.docker.example .env.docker
# заполнить переменные
.\scripts\docker-up.ps1
.\scripts\smoke-local.ps1
```

## Тесты

**[PowerShell]**
```powershell
.\scripts\check.ps1
```

**[WSL2]**
```bash
./scripts/check.sh
```

## Структура monorepo

```
Ruza/
├── icebeach-wakeclub/
│   ├── apps/api/          # FastAPI
│   ├── apps/dashboard/    # React
│   ├── apps/edge/voice/   # on-device voice prototype
│   └── packages/sheets/   # SheetWrapper + schema
├── docs/                  # архитектура, схема Sheets, security
├── scripts/               # start/stop/smoke/docker
└── .cursor/rules/         # agents + skills
```

## Cursor Agents

| Agent | Зона |
|-------|------|
| agent-00 Orchestrator | план, интеграция, DoD |
| agent-01 Backend | API, Sheets, booking |
| agent-02 Frontend | dashboard, role views |
| agent-03 Edge | voice/face on-device |
| agent-04 Analytics | KPI, snapshots |
| agent-05 Marketing | leads, funnel |
| agent-06 DevOps | hooks, Docker, staging |

## Документация

- **[docs/MYWAVE_NORTH_STAR.md](docs/MYWAVE_NORTH_STAR.md)** — путеводная звезда команды (стратегия MyWave → приоритеты Ruza)
- [docs/SHEETS_SCHEMA.md](docs/SHEETS_SCHEMA.md) — контракт табов
- **[docs/SERVER_COMMANDS.md](docs/SERVER_COMMANDS.md)** — команды для VPS / Timeweb / Docker
- [docs/STAGING_DEPLOY.md](docs/STAGING_DEPLOY.md) — staging runbook
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/TEST_PLAN.md](docs/TEST_PLAN.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- Staging: [icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md](icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md)

## Git policy

- `commit` — разрешён агентом
- `push` — заблокирован хуком; оператор: `$env:ALLOW_GIT_PUSH=1; git push`
