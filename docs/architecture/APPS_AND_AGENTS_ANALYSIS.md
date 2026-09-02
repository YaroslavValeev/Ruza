# Анализ приложений и AI Agents — Ice Beach / Ruza

> North Star: [`MYWAVE_NORTH_STAR.md`](../MYWAVE_NORTH_STAR.md)

## 1. Текущая база

| Слой | Статус |
|------|--------|
| Desktop dashboard | MVP: брони, KPI, маркетинг, пилот |
| Mobile PWA `/m/pilot`, `/m/owner` | Стабилизация LAN |
| Google Sheets SoT | MVP + audit_log |
| Edge voice CLI | Прототип, без UI |
| Операционные agents | `apps/agents/` + internal API |

## 2. Восемь направлений рынка

1. **Клиентское приложение** — виджет `/book` (post-MVP в фазе 5)
2. **Оператор** — экран `/shift` «Смена сегодня»
3. **Пилот** — mobile queue + Queue Coach
4. **Owner** — KPI + brief + алерты
5. **Платежи** — payment ledger + KPI по фактическим оплатам
6. **Маркетинг** — leads, funnel, LTV карточка
7. **Доверие** — consent_face/voice, audit
8. **Инфра** — Docker, smoke, agents scheduler

## 3. Dev Subagents (Cursor)

| ID | Роль | Scope |
|----|------|-------|
| agent-00 | Orchestrator | sequencing, DoD, gates |
| agent-01 | Backend | FastAPI, Sheets, internal agents API |
| agent-02 | Frontend | React cards, mobile, shift UI |
| agent-03 | Edge | voice FSM, on-device |
| agent-04 | Analytics | KPI, snapshot, daily brief |
| agent-05 | Marketing | leads, LTV, public book |
| agent-06 | DevOps | scripts, smoke, scheduler |

## 4. Операционные Agents (runtime)

| Agent | Тип | Триггер |
|-------|-----|---------|
| PreflightGuard | детерминированный | перед сменой / cron |
| LateMarker | детерминированный | каждые 5 мин 08–22 |
| ShiftSnapshot | детерминированный | 22:05 |
| OpsAlert | notify | health/preflight fail |
| DailyBrief | notify | 07:00 / 22:10 |
| QueueCoach | UI | пилотский экран |

Approve на критичные действия — см. [`packages/shared-policy/approval_rules.yaml`](../../packages/shared-policy/approval_rules.yaml).

## 5. Критерий успеха

- production local audit green: `scripts/production-v1-local-audit.ps1`
- smoke green + agents-smoke green
- полевой тест pilot + owner на LAN
- brief/алерты в log или Telegram
