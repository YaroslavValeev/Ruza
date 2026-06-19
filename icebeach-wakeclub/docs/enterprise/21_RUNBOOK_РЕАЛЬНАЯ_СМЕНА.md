# Runbook: real pilot shift

## Purpose
This runbook is for one real shift in controlled pilot mode.
It defines:
- who clicks what
- the order of actions during the shift
- what to do when `Failed to fetch` appears

## Roles
- `admin`: starts local services, checks access, makes go/no-go decision
- `operator`: finds or creates client, creates booking, checks in client, moves booking to `ready`
- `pilot`: opens queue for assigned boat, moves booking `in_progress -> done`

## Pre-shift checklist
- `API` and `Dashboard` are running locally
- `staff_users` contains active staff with valid `staff_user_id`, `club_id`, `role`, `phone`
- `boats` contains active boat, for example `boat_001`
- `schedule` contains an active slot for the shift date
- `pricing` contains a row with matching `club_id` and `valid_from <= shift date`
- `bookings`, `analytics_daily`, `audit_log`, `auth_codes`, `slot_overrides` tabs exist

## Opening the shift: admin
1. Open `PowerShell`.
2. Run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "F:\Проекты MyWave\NEW2026\Ruza\scripts\start-local.ps1"
   ```
3. Open [health](http://127.0.0.1:8001/health).
4. Confirm response is `{"status":"ok"}`.
5. Open [dashboard](http://127.0.0.1:5173).
6. Log in as staff:
   - enter `staff_user_id`
   - enter phone in `+7...` format
   - click `Получить код`
   - enter code
7. Open `KPI` and confirm the page loads.
8. Open `Брони` and confirm the required slot is visible.
9. If the slot is missing, open `Google Sheets` and verify `schedule`, `boats`, `pricing`.

## Operator flow
1. Open `Брони`.
2. Search the client by name or phone.
3. If the client does not exist:
   - fill `Имя клиента`
   - fill `Телефон`
   - click `Создать клиента`
4. In `Бронь`:
   - select date
   - confirm selected client
   - select slot, for example `10:00 - boat_001`
   - enable `Тренер нужен` if required
   - add note if needed
   - click `Создать бронь`
5. Confirm booking appears in `Брони дня` with status `confirmed`.
6. When client arrives, click `arrived`.
7. When client is dressed, briefed, and ready, click `ready`.
8. If client is late:
   - first use `late`
   - then either `arrived` or `no_show`
9. If booking is cancelled before start, click `cancelled`.

## Pilot flow
1. Open `Pilot`.
2. In the boat field, enter exact `boat_id`, for example `boat_001`.
3. Select shift date.
4. Click `Загрузить очередь`.
5. Find the booking with status `ready`.
6. At actual start, click `in_progress`.
7. At actual finish, click `done`.
8. If queue is empty:
   - recheck exact `boat_id`
   - recheck date
   - ask operator to confirm booking is already in `ready`

## Single-session sequence
1. `operator`: create booking -> `confirmed`
2. `operator`: client arrived -> `arrived`
3. `operator`: client prepared -> `ready`
4. `pilot`: start -> `in_progress`
5. `pilot`: finish -> `done`
6. `admin`: verify `KPI` and `audit_log` if needed

## What to monitor in Google Sheets during the shift
- `bookings`: new row is created, `status` changes, `updated_at` changes
- `audit_log`: `create booking`, `update booking`, and login events are appended
- `analytics_daily`: KPI consistency after dry-run or after real shift

## If `Failed to fetch` appears
The usual causes are:
- API is not running
- API crashed or hung
- connection to `127.0.0.1:8001` was interrupted

### Fast recovery
1. Open a new browser tab.
2. Open [health](http://127.0.0.1:8001/health).
3. If `health` does not respond:
   - open `PowerShell`
   - run:
     ```powershell
     powershell -ExecutionPolicy Bypass -File "F:\Проекты MyWave\NEW2026\Ruza\scripts\start-local.ps1"
     ```
   - wait 10-20 seconds
   - open [health](http://127.0.0.1:8001/health) again
4. Return to `Dashboard`.
5. Press `Ctrl + F5`.
6. Repeat the failed action.

### If login fails
- confirm [health](http://127.0.0.1:8001/health) responds
- confirm `staff_users.phone` matches the entered phone
- enter phone in `+7...` format

### If slot loading fails
- verify `pricing`
- verify `schedule`
- verify `boats`
- verify shift date matches slot date

### If booking creation fails
- if error contains `No pricing configured`, fix `pricing`
- if slot disappeared, refresh page and reload availability
- if booking may already exist, check `bookings` tab and `Брони дня`

## Go / No-Go
`GO` if:
- login works
- slot is visible
- booking is created
- `arrived -> ready -> in_progress -> done` works without manual sheet edits
- `bookings` and `audit_log` update correctly

`NO-GO` if:
- [health](http://127.0.0.1:8001/health) is unavailable
- no slots exist for shift date
- booking cannot be created
- pilot queue cannot see booking with correct `boat_id`
- statuses in UI and `bookings` diverge

## Closing the shift
1. Open `KPI`.
2. Check sessions count and revenue.
3. Open `bookings` and confirm active bookings are closed.
4. Open `audit_log` and confirm status transitions are logged.
5. Stop local services:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "F:\Проекты MyWave\NEW2026\Ruza\scripts\stop-local.ps1"
   ```
