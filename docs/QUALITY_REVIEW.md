# Quality review — стадия Ruza / Ice Beach

Дата: 2026-08-20  
Контур: **MyWave Training / Cash-cow** (`booking → check-in → pilot → KPI`)

## 1. На какой мы стадии

Это **Sprint 1 (деньги сейчас) + зачатки Sprint 3 (лиды/воронка)**.

| Слой | Статус |
|------|--------|
| Google Sheets как SoT | Канон зафиксирован, live staging зависит от credentials |
| FastAPI booking/check-in/pilot/KPI | MVP есть, контрактные тесты закрывают ядро смены |
| React dashboard (роли) | MVP есть; UX смены доведён в этом проходе |
| Auth по SMS-коду | Код есть; боевая доставка OTP **ещё не подключена** |
| Voice admin on-device | Прототип, не блокер Cash-cow |
| Staging Timeweb | Чеклист есть, GO после 2× green smoke на live Sheets |
| SponsorOS / Gear / Desktop Personal_Helper | Вне текущего репо, не трогаем |

**DoD Orchestrator ещё не закрыт на боевых Sheets:** local Docker/staging требуют `SPREADSHEET_ID` и service account. В этом окружении проверка идёт через in-memory demo + pytest.

## 2. Специалисты, которых подключили

| Роль | Вывод |
|------|--------|
| UX (сменный UI) | 5/10 до правок: вход по `staff_user_id`, check-in без подтверждения брони, пилот смешивает роли оператора |
| Backend | CI красный (`httpx`/`get_settings` на импорте), availability рисовала 30 слотов вне schedule |
| Security / DevOps | OTP debug в Docker example, hooks без +x, секреты в git history (`1.txt`/`2.txt`) — нужна ротация человеком |
| Analytics | KPI считал не `done`, а все активные брони; воронка `contacted` не копила `booked` |
| Marketing | Экран выпадал из визуальной системы, период сезона не был виден |

## 3. Что исправлено в этом проходе

- CI: pinned FastAPI/httpx, app больше не падает на импорте без Google env
- Слоты только из `schedule` (если расписание заполнено)
- Check-in пишет бронь только после валидного FSM; `cancelled` больше не превращается в `late`
- Вход по телефону, OTP rate-limit на verify
- Пилот не стартует чужую лодку и не делает arrive/ready
- UX: login, nav, check-in с подтверждением, очередь раньше формы, лодки списком, NO-GO на KPI
- Demo API без Google: `scripts/demo_local.py`

## 4. Что сознательно отложено

- Боевая доставка OTP (SMS/Telegram)
- Конкурентные записи в Sheets (single-writer)
- Мультиклубный snapshot_id
- Frontend unit/a11y автотесты
- CAC attribution и UTM public ingest

## 5. Критерий готовности к пилотной смене

1. pytest зелёный  
2. dashboard build зелёный  
3. demo: login → бронь → arrived → ready → in_progress → done  
4. На staging: 2× smoke + preflight без blockers
