# Google Sheets — недостающие вкладки для check-in и KPI

Если smoke падает с:

```
Missing or misnamed sheet tab: checkins
Missing or misnamed sheet tab: kpi_targets
```

Добавьте в вашу таблицу (`SPREADSHEET_ID` из `.env`) операционные вкладки через
идемпотентный bootstrap. Команда создаёт только отсутствующие вкладки и не
перезаписывает существующие строки:

```powershell
$env:PYTHONPATH=(Resolve-Path .\icebeach-wakeclub).Path
python -m packages.sheets.bootstrap_tabs
```

---

## Автоматически (рекомендуется)

**[PowerShell]**

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\sheets-bootstrap.ps1
.\scripts\smoke-local.ps1
```

Скрипт создаёт вкладки `checkins` и `kpi_targets`, пишет заголовки и пример строки KPI.

---

## Вручную (если bootstrap недоступен)

**Строка 1 (заголовки, скопируйте в A1):**

```
checkin_id	club_id	booking_id	client_id	method	status	ts	operator_user_id
```

| Колонка | Пример |
|---------|--------|
| checkin_id | chk-uuid |
| club_id | ice_beach_ruza |
| booking_id | bkg-... |
| client_id | client-... |
| method | phone / manual / system |
| status | arrived / ready / late |
| ts | ISO datetime UTC |
| operator_user_id | staff_user_id |

Данные пишет API автоматически — строки вручную не нужны.

---

## 2. Вкладка `kpi_targets`

**Строка 1 (заголовки):**

```
target_id	club_id	period	sessions_target	utilization_target_pct	revenue_target
```

**Пример строки 2 (сезон 2026):**

```
tgt-2026-season	ice_beach_ruza	2026-06	120	75	500000
```

`period` для сезона: `YYYY-06` (июнь якорь). Для месяца: `YYYY-MM`.

---

## 3. Проверка

**[PowerShell]**

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\smoke-local.ps1
```

Preflight теперь тоже проверяет эти вкладки — при отсутствии будет **BLOCKER** до создания брони.

Полная схема: `icebeach-wakeclub/packages/sheets/schema.py`
