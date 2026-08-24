# Ruza — Ice Beach Wake Club Automation

Цифровая экосистема клуба «Айс пляж» (Руза): Google Sheets как единственный источник истины, FastAPI backend, React dashboard.

## Режим работы

**Сейчас: Docker на компьютере** (разработка и проверка до удовлетворения).  
**Потом: сервер** — см. [docs/SERVER_COMMANDS.md](docs/SERVER_COMMANDS.md).

---

## Docker — основной способ (рекомендуется)

**[PowerShell]**

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"

# Нужны: .env + service-account.json в корне репо

# DEV: hot reload API + Vite dashboard
.\scripts\docker-up.ps1 -Dev

# Проверка
.\scripts\docker-status.ps1 -Dev
.\scripts\smoke-local.ps1

# Остановка
.\scripts\docker-down.ps1 -Dev
```

| URL | Сервис |
|-----|--------|
| http://127.0.0.1:8000/health | API |
| http://127.0.0.1:5173 | Dashboard |

Подробно: **[docs/DOCKER_LOCAL.md](docs/DOCKER_LOCAL.md)**

---

## Альтернатива: без Docker (start-local.ps1)

**[PowerShell]**

```powershell
pip install -r icebeach-wakeclub\apps\api\requirements.txt
cd icebeach-wakeclub\apps\dashboard; npm install; cd ..\..\..
.\scripts\start-local.ps1
```

---

## Стек

- **Backend:** Python 3.11, FastAPI, Google Sheets API
- **Frontend:** React 18, Vite 5, Tailwind CSS
- **Auth:** RBAC по `staff_users` в Sheets, cookie session + SMS-код
- **Deploy:** локально Docker → позже VPS / Timeweb

## Тесты

**[PowerShell]**

```powershell
$env:PYTHONPATH="f:\Проекты MyWave\NEW2026\Ruza\icebeach-wakeclub"
python -m pytest icebeach-wakeclub\apps\api\tests -v
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
- **[docs/DOCKER_LOCAL.md](docs/DOCKER_LOCAL.md)** — Docker-first разработка
- **[docs/SERVER_COMMANDS.md](docs/SERVER_COMMANDS.md)** — когда будете готовы к VPS
- [docs/STAGING_DEPLOY.md](docs/STAGING_DEPLOY.md) — staging runbook
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/TEST_PLAN.md](docs/TEST_PLAN.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- Staging: [icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md](icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md)

## Git policy

- `commit` — разрешён агентом
- `push` — заблокирован хуком; оператор: `$env:ALLOW_GIT_PUSH=1; git push`
