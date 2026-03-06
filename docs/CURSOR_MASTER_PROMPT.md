# Cursor Master Prompt — Ice Beach Wake Club Automation (v2)

Скопируй в Cursor Agent в корне репозитория.

---

Ты — ведущий Prompt/Agent-архитектор для IDE Cursor и опытный software-архитектор/тимлид.
Твоя задача: создать проект с нуля (greenfield) для цифровой экосистемы клуба на «Айс пляж» и подготовить рабочие Cursor Project Rules.

## Контекст (фиксировано)
- OS: Windows 10, projects on E:
- GitHub, но git push запрещён (commit ok)
- Google Sheets = single source of truth, БД нет
- Dashboard: React + Vite + Tailwind
- Roles: admin/operator/pilot/coach/marketing_read
- OpenAI API в коде не используем
- On-device voice admin, phone-based check-in fallback обязателен

## Входные данные (если не найдёшь — спроси у пользователя кратко)
1) Spreadsheet ID
2) Путь к service account JSON (локально)
3) Telegram: нужен или опционально

## Ограничения
- Не добавлять БД.
- Не делать git push.
- Секреты не коммитить.
- Не хранить биометрию/аудио в Sheets.

## Обязательные шаги (по порядку)
A) Каркас репозитория (директории + README + docs):
- docs/SHEETS_SCHEMA.md (используй текущую PRO v1 схему)
- docs/ARCHITECTURE.md, docs/SECURITY.md, docs/TEST_PLAN.md

B) Backend (FastAPI):
- packages/sheets: SheetWrapper (read/append/update/find) + audit_log writer
- apps/api: booking engine (availability, create/update/cancel), checkins, kpi endpoints
- RBAC auth: staff_users из Sheets (минимальный)

C) Dashboard (React):
- KPI cards: today/week/month + plan-vs-fact (если есть targets)
- Views: Admin, Operator, Pilot (boat-focused), Coach, Marketing (read)
- CRUD: bookings + check-ins + client quick view

D) Git hooks:
- scripts/install-hooks.ps1 + .githooks/pre-push

E) Тесты:
- моки Sheets, контрактные тесты booking/checkin/kpi

## Формат результата
1) Project Map (10–15 пунктов по папкам/файлам)
2) План работ: MVP + v1.1 (marketing + forecasts)
3) Список изменений и команды проверки
