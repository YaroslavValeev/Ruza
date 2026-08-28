# Quality review — стадия Ruza / Ice Beach

Дата: 2026-08-28
Контур: **MyWave Training / Cash-cow** (`booking → check-in → pilot → KPI`)

## 1. На какой мы стадии

Это **Sprint 1 (деньги сейчас) + зачатки Sprint 3 (лиды/воронка)**.

| Слой | Статус |
|------|--------|
| Google Sheets как SoT | Канон зафиксирован, live staging зависит от credentials |
| FastAPI booking/check-in/pilot/KPI | MVP есть, контрактные тесты закрывают ядро смены |
| React dashboard (роли) | MVP есть; UX смены и воронки лидов доведены в этом проходе |
| Auth по SMS-коду | Код есть; Telegram OTP-адаптер готов, но токен не задаём до ротации секретов |
| Voice admin on-device | Прототип FSM, не блокер Cash-cow |
| Staging Timeweb | Чеклист есть, GO после 2× green smoke на live Sheets |
| SponsorOS / Gear / Desktop Personal_Helper | Вне текущего репо, не трогаем |

**DoD Orchestrator ещё не закрыт на боевых Sheets:** local Docker/staging требуют `SPREADSHEET_ID` и service account. В этом окружении проверка идёт через in-memory demo + pytest.

## 2. Специалисты, которых подключили

| Роль | Вывод |
|------|--------|
| UX (сменный UI) | 5/10 до правок: вход по `staff_user_id`, check-in без подтверждения брони, пилот смешивает роли оператора |
| Backend | CI красный (`httpx`/`get_settings` на импорте), availability рисовала 30 слотов вне schedule |
| Security / DevOps | OTP debug в Docker example, hooks без +x, секреты в git history (`1.txt`/`2.txt`) |
| Analytics | KPI считал не `done`, а все активные брони; snapshot мог затирать чужой `club_id` |
| Marketing | Экран выпадал из визуальной системы, не было смены статуса лида |

## 3. Что исправлено в этом проходе

### Волна 1
- CI: pinned FastAPI/httpx, app больше не падает на импорте без Google env
- Слоты только из `schedule` (если расписание заполнено)
- Check-in пишет бронь только после валидного FSM; `cancelled` больше не превращается в `late`
- Вход по телефону, OTP rate-limit на verify
- Пилот не стартует чужую лодку и не делает arrive/ready
- UX: login, nav, check-in с подтверждением, очередь раньше формы, лодки списком, NO-GO на KPI
- Demo API без Google: `scripts/demo_local.py`

### Волна 2 (без ротации секретов)
- Сессия сверяет живую роль и `is_active` из `staff_users`
- Face check-in требует `consent_face`
- `in_progress` → только `done` (оператор не может отменить заезд на воде)
- Analytics snapshot keyed по `(date, club_id)`
- UTM write только admin/operator
- OTP: канал `telegram` если задан `TELEGRAM_BOT_TOKEN`, иначе `manual`
- Production invariant: debug OTP и legacy login запрещены при `APP_ENV=production`
- Marketing: создание лида и смена статуса для admin/operator
- Бейджи `ready` / `in_progress` заметнее на экране смены
- CI dashboard: `npm ci`; pre-commit ищет `python3`, затем `python`
- Demo-запуск без Google: `scripts/start-demo.ps1` / `scripts/start-demo.sh`
- Локальная дата смены (не UTC), кнопки demo-ролей на логине, `scripts/smoke_demo.py`

### Волна 3 (production-v1 release candidate)

- Source of Truth: внешний intake идёт через canonical MyWave sheet → `RuzaTab.leads`, без автосоздания брони.
- Payment ledger: `payments` + `payment_closures`, API записи/возвратов, KPI считает `payments_gross_minor` / `net_revenue_minor`.
- Release gates: clean-tree guard, production env guard, PR #4, tag `v1.0.0-rc.9`, локальный production audit.
- Production env validation: Windows и Linux скрипты блокируют debug OTP, manual OTP, insecure cookie, localhost CORS и placeholder values перед deploy.

## 4. Что сознательно отложено владельцем / внешним контуром

- **Ротация секретов из git history** — только после завершения всех текущих работ
- Боевой Telegram/SMS OTP (адаптер есть, production требует HTTPS webhook/token)
- Конкурентные записи в Sheets (single-writer)
- Timeweb staging/prod, HTTPS, monitoring/alerting и rollback drill
- Restore-write в отдельную staging-таблицу
- Live website/TG intake delivery proof
- iOS Safari smoke на HTTPS URL
- Frontend unit/a11y автотесты
- CAC attribution и UTM public ingest
- SponsorOS / Gear / слияние Personal_Helper–Agents–Molt

## 5. Критерий готовности к пилотной смене

1. pytest зелёный
2. dashboard build зелёный
3. demo: login → бронь → arrived → ready → in_progress → done
4. `scripts/production-v1-local-audit.ps1` без local blockers
5. На staging: 2× smoke + preflight без blockers
6. После закрытия работ: ротация секретов человеком, затем production OTP provider
