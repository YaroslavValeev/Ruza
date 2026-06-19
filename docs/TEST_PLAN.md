# Test Plan — Ice Beach Wake Club (MVP)

## Уровни

### 1. Contract tests (pytest, mock Sheets)

Путь: `icebeach-wakeclub/apps/api/tests/`

| Тест | Сценарий |
|------|----------|
| `test_auth_code_flow_and_me` | request-code → verify → /auth/me |
| `test_availability_contract` | слоты на дату |
| `test_booking_contract_writes_audit_and_price` | create + audit + pricing |
| `test_booking_no_overbook` | 409 при переполнении |
| `test_booking_status_transition_and_pilot_queue` | FSM + pilot queue |
| `test_booking_rbac_pilot_forbidden` | pilot не создаёт брони |
| `test_checkin_by_phone` | check-in по телефону |
| `test_checkin_mark_late` | mark-late endpoint |

Запуск:

**[PowerShell]**
```powershell
$env:PYTHONPATH="f:\Проекты MyWave\NEW2026\Ruza\icebeach-wakeclub"
python -m pytest icebeach-wakeclub/apps/api/tests -v
```

### 2. Smoke (live API + Sheets)

**[PowerShell]**
```powershell
.\scripts\start-local.ps1
.\scripts\smoke-local.ps1 -Date "2026-06-10"
```

Проверяет: health, auth, preflight, availability, clients, booking CRUD, pilot, KPI.

### 3. Preflight (integrity gate)

**[PowerShell]**
```powershell
.\scripts\preflight-local.ps1 -Date "2026-06-01"
```

Или API: `GET /preflight/summary?date=` (admin).

### 4. Staging gate

См. `icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md`:
- 2× green smoke подряд
- ручной цикл `booking → ready → in_progress → done`

### 5. Frontend (CI)

- `npm run build` — production build
- `npx tsc --noEmit` — typecheck

## Quality gates

- Изменения в booking/checkin/kpi без contract-тестов — не принимаются
- Перед staging: preflight blockers = 0
- Секреты не в репозитории
