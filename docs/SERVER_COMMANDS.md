# Команды для сервера — Ice Beach / Ruza

Копируй блоки по порядку. Метки: **[PowerShell]** — Windows, **[Linux]** — VPS/Ubuntu.

**Актуализация 2026-10-05:** основной production-like контур — **VPS + docker compose**
в `/opt/icebeach` (контейнеры `icebeach-api-1`, `icebeach-dashboard-1`). Host (Owner):
`root@4169037-ep26382`. Checkout для обновлений: `origin/main` или **новый** annotated tag
на нужный SHA (например будущий `v1.0.0-rc.20`). Tag `v1.0.0-rc.19` → `51180f3` **отстаёт**
от main `bd77c197` и не должен быть единственной целью checkout. Этот документ не является
разрешением на deploy — только Owner GO. Секреты не ротировать из агентских сессий.

**Актуализация 2026-10-07 MSK:** публичный URL — `https://ruza.mywavewake.ru` (nginx +
Let's Encrypt, cert до 2027-01-04, auto-renew). Evidence по воротам — в
[PRODUCTION_V1_GATES.md](PRODUCTION_V1_GATES.md) §8. Ниже `dashboard.example.com` в
шаблонах соответствует `ruza.mywavewake.ru`.


---

## 0. Что поднять

| Вариант | Когда |
|---------|--------|
| **A. Timeweb App Platform** | Быстрый staging без SSH (GitHub + Dockerfile) |
| **B. VPS + Docker compose (primary)** | `/opt/icebeach`, nginx, SSL, API + dashboard |

Dockerfile API: `icebeach-wakeclub/Dockerfile`  
Порт API: **8000**  
Health: **GET /health**

---

## 1. Подготовка на Windows (перед сервером)

### 1.1 Google credentials в base64 (для env на сервере)

**[PowerShell]**
```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
$bytes = [IO.File]::ReadAllBytes("service-account.json")
$env:GOOGLE_SA_B64 = [Convert]::ToBase64String($bytes)
# Скопировать в буфер:
$env:GOOGLE_SA_B64 | Set-Clipboard
Write-Host "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 скопирован в буфер ($($env:GOOGLE_SA_B64.Length) символов)"
```

### 1.2 Push в GitHub (оператор)

**[PowerShell]**
```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
git status --short --branch
git fetch origin
git rev-parse HEAD origin/main
git tag --points-at HEAD
# push branch / tags только с ALLOW_GIT_PUSH=1 и после Owner GO
$env:ALLOW_GIT_PUSH=1
git push origin HEAD
# optional, Owner only:
# git tag -a v1.0.0-rc.20 bd77c197 -m "Ruza RC20: main after PR #7"
# git push origin v1.0.0-rc.20
```

---

## 2. Вариант A — Timeweb App Platform (без SSH)

В панели Timeweb → Apps → GitHub → репозиторий **Ruza**:

| Параметр | Значение |
|----------|----------|
| Dockerfile path | `icebeach-wakeclub/Dockerfile` |
| Build context | `icebeach-wakeclub` |
| Port | `8000` |
| Health path | `/health` |

**Env (минимум):**
```env
APP_ENV=production
SPREADSHEET_ID=<ваш_id>
INTAKE_SPREADSHEET_ID=<id_таблицы_заявок>
INTAKE_TAB_NAME=Ruza
SESSION_SECRET=<длинная_случайная_строка>
SESSION_COOKIE_SECURE=true
ALLOW_LEGACY_STAFF_LOGIN=false
AUTH_DEBUG_CODE_IN_RESPONSE=false
ALLOW_MANUAL_OTP_DELIVERY=false
# Production OTP: TELEGRAM_BOT_TOKEN и/или HTTPS SMS webhook
TELEGRAM_BOT_TOKEN=<если_используете_telegram>
OTP_DELIVERY_WEBHOOK_URL=
OTP_DELIVERY_WEBHOOK_TOKEN=
OTP_DELIVERY_TIMEOUT_SECONDS=8
DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true
SHEETS_TAB_CACHE_TTL_SECONDS=15
CORS_ALLOW_ORIGINS=https://<ваш-dashboard-домен>
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=<из_шага_1.1>
API_HOST=0.0.0.0
API_PORT=8000
```

**Проверка backend после деплоя [Linux/curl с любой машины]:**
```bash
curl -sS https://<api-domain>/health
```

Для доступа с iOS Safari потребуется отдельно развернуть dashboard с HTTPS и
`VITE_API_BASE_URL=/api` либо эквивалентным same-origin reverse proxy.

Подробнее: [22_TIMEWEB_BACKEND_DEPLOY.md](../icebeach-wakeclub/docs/enterprise/22_TIMEWEB_BACKEND_DEPLOY.md)

---

## 3. Вариант B — VPS Ubuntu (рекомендуется для production-like)

### 3.1 Первичная установка Docker

**[Linux]** — под root или sudo:
```bash
apt update && apt upgrade -y
apt install -y ca-certificates curl git ufw

# Docker (official)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo ${VERSION_CODENAME}) stable" > /etc/apt/sources.list.d/docker.list
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

mkdir -p /opt/icebeach
```

### 3.2 Клонирование репозитория

**[Linux]**
```bash
cd /opt/icebeach
# если репозиторий ещё не клонирован:
# git clone https://github.com/YaroslavValeev/Ruza.git .
git fetch --tags origin
# предпочтительно: tip main или новый tag, указывающий на нужный SHA
git checkout --detach origin/main
# альтернатива после Owner tag GO:
# git checkout v1.0.0-rc.20
# НЕ использовать v1.0.0-rc.19 как единственную цель: он указывает на 51180f3 (behind main)
```

### 3.3 Production env на сервере

**[Linux]**
```bash
cd /opt/icebeach
cp .env.docker.example .env.docker
nano .env.docker
```

Перед любым запуском проверьте, что в `.env.docker` нет local/debug настроек:

```bash
bash scripts/server/validate-production-env.sh .env.docker
```

`deploy-api.sh` запускает эту проверку автоматически и остановит deploy, если включен debug OTP,
manual OTP, insecure cookie, localhost CORS или placeholder values.

Заполните (пример содержимого):
```env
APP_ENV=production
SPREADSHEET_ID=1Jos8absjdLueLoWXZDJS67PRHXfrQ-fnTq-yiXk2_18
INTAKE_SPREADSHEET_ID=1kyNQVjeLLe4Ra6oWuf84fHqSjUlWXI8MakVMOrCgic0
INTAKE_TAB_NAME=Ruza
SESSION_SECRET=ЗАМЕНИТЕ_НА_OPENSSL_RAND
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_NAME=icebeach_session
ALLOW_LEGACY_STAFF_LOGIN=false
AUTH_DEBUG_CODE_IN_RESPONSE=false
ALLOW_MANUAL_OTP_DELIVERY=false
# Production OTP: либо HTTPS SMS webhook+token, либо TELEGRAM_BOT_TOKEN (webhook может быть пустым)
TELEGRAM_BOT_TOKEN=
OTP_DELIVERY_WEBHOOK_URL=
OTP_DELIVERY_WEBHOOK_TOKEN=
OTP_DELIVERY_TIMEOUT_SECONDS=8
DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true
SHEETS_TAB_CACHE_TTL_SECONDS=15
CORS_ALLOW_ORIGINS=https://dashboard.example.com
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=ВСТАВИТЬ_BASE64
API_HOST=0.0.0.0
API_PORT=8000
```

Сгенерировать `SESSION_SECRET`:
```bash
openssl rand -hex 32
```

### 3.4 Запуск API + Dashboard (docker compose) — primary на VPS `/opt/icebeach`

Dashboard собирается с `VITE_API_BASE_URL=/api`: браузер ходит на тот же HTTPS-домен,
а dashboard nginx проксирует `/api/` в backend container. Это уменьшает CORS/cookie
риски на iOS Safari.

**[Linux]**
```bash
cd /opt/icebeach
bash scripts/server/assert-clean-release-tree.sh
bash scripts/server/validate-production-env.sh .env.docker
docker compose --env-file .env.docker up --build -d
docker compose ps
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:5173/api/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5173/
```

### 3.5 Nginx + SSL (Let's Encrypt)

**[Linux]**
```bash
apt install -y nginx certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/icebeach <<'NGINX'
server {
    listen 80;
    server_name dashboard.example.com;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

NGINX

ln -sf /etc/nginx/sites-available/icebeach /etc/nginx/sites-enabled/icebeach
nginx -t && systemctl reload nginx

certbot --nginx -d dashboard.example.com
```

Проверка сертификата и auto-renew (prod: `ruza.mywavewake.ru`, expires 2027-01-04):

```bash
certbot certificates
certbot renew --dry-run
systemctl list-timers | grep -i certbot
```

После SSL обновите `CORS_ALLOW_ORIGINS` в `.env.docker` и перезапустите API:
```bash
cd /opt/icebeach
grep -q '^CORS_ALLOW_ORIGINS=https://dashboard.example.com$' .env.docker || echo 'Проверьте CORS_ALLOW_ORIGINS вручную'
docker compose --env-file .env.docker up -d --force-recreate api dashboard
```

---

## 4. Обслуживание на сервере

### Обновление кода

**[Linux]**
```bash
cd /opt/icebeach
git fetch --tags origin
git checkout --detach origin/main
# или: git checkout v1.0.0-rc.<new>   # только если tag указывает на нужный SHA
bash scripts/server/assert-clean-release-tree.sh
bash scripts/server/validate-production-env.sh .env.docker
docker compose --env-file .env.docker up --build -d
docker compose ps
# ожидаемые сервисы: icebeach-api-1, icebeach-dashboard-1
curl -sS https://dashboard.example.com/api/health
```

### Логи и статус

**[Linux]**
```bash
docker ps
docker compose -f /opt/icebeach/docker-compose.yml logs -f api dashboard
```

### Monitoring healthcheck

Read-only проверка API/dashboard с записью лога:

**[Linux]**
```bash
cd /opt/icebeach
mkdir -p /var/log/ruza
bash scripts/server/healthcheck.sh \
  --api-url "https://dashboard.example.com/api" \
  --dashboard-url "https://dashboard.example.com" \
  --log-file "/var/log/ruza/healthcheck.log"
```

Cron каждые 5 минут (вариант с generic webhook):

```bash
(crontab -l 2>/dev/null; echo '*/5 * * * * cd /opt/icebeach && bash scripts/server/healthcheck.sh --api-url "https://dashboard.example.com/api" --dashboard-url "https://dashboard.example.com" --log-file "/var/log/ruza/healthcheck.log" --alert-webhook-url "https://alert-webhook.example/ruza"') | crontab -
```

#### Telegram alert на смену состояния (prod, установлено 2026-10-06/07)

На prod используется обёртка `/usr/local/bin/ruza-healthcheck-alert.sh`: запускает
`scripts/server/healthcheck.sh`, хранит последнее состояние (`OK`/`FAIL`) в
`/var/lib/ruza/health.state` и шлёт Telegram DM через Ruza bot **только при смене
состояния** (падение и восстановление). Токен бота и chat id читаются из
`/opt/icebeach/.env.docker` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`) — в скрипт
и в git токен не вписывается. Evidence: тестовый прогон `rc=0`, recovery-сообщение получено.

Эталонное содержимое (если копия на VPS — `cat /usr/local/bin/ruza-healthcheck-alert.sh` —
отличается, источник истины — VPS; обновите этот блок):

**[Linux]**
```bash
install -d -m 0755 /var/lib/ruza /var/log/ruza
cat > /usr/local/bin/ruza-healthcheck-alert.sh <<'SCRIPT'
#!/usr/bin/env bash
# Ruza healthcheck -> Telegram DM only on state change (OK <-> FAIL).
set -uo pipefail

APP_DIR="/opt/icebeach"
ENV_FILE="${APP_DIR}/.env.docker"
BASE_URL="https://ruza.mywavewake.ru"
STATE_FILE="/var/lib/ruza/health.state"
LOG_FILE="/var/log/ruza/healthcheck.log"

read_env() {
  # Read one KEY=value from .env.docker without sourcing the whole file.
  grep -E "^$1=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//'
}

mkdir -p "$(dirname "${STATE_FILE}")" "$(dirname "${LOG_FILE}")"

output="$(cd "${APP_DIR}" && bash scripts/server/healthcheck.sh \
  --api-url "${BASE_URL}/api" \
  --dashboard-url "${BASE_URL}" \
  --log-file "${LOG_FILE}" 2>&1)"
rc=$?
if [[ ${rc} -eq 0 ]]; then current="OK"; else current="FAIL"; fi

previous="$(cat "${STATE_FILE}" 2>/dev/null || echo UNKNOWN)"
if [[ "${current}" != "${previous}" ]]; then
  if [[ "${current}" == "OK" ]]; then
    text="✅ Ruza OK: ${BASE_URL} healthcheck recovered"
  else
    text="🔴 Ruza FAIL (rc=${rc}): $(printf '%s\n' "${output}" | grep -E '^\[BLOCKER\]|^SUMMARY' | head -n 5)"
  fi
  token="$(read_env TELEGRAM_BOT_TOKEN)"
  chat_id="$(read_env TELEGRAM_OWNER_CHAT_ID)"
  if [[ -n "${token}" && -n "${chat_id}" ]]; then
    # URL with the token goes via curl config on stdin, not argv (not visible in ps).
    if printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "${token}" | \
      curl -fsS --max-time 10 --config - \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${text}" >/dev/null; then
      echo "${current}" > "${STATE_FILE}"
    fi
  fi
fi

exit "${rc}"
SCRIPT
chmod 0755 /usr/local/bin/ruza-healthcheck-alert.sh

# тестовый прогон: rc=0 и (при смене состояния) сообщение в Telegram
/usr/local/bin/ruza-healthcheck-alert.sh; echo "rc=$?"; cat /var/lib/ruza/health.state

# cron каждые 5 минут
(crontab -l 2>/dev/null | grep -v ruza-healthcheck-alert; echo '*/5 * * * * /usr/local/bin/ruza-healthcheck-alert.sh >/dev/null 2>&1') | crontab -
crontab -l | grep ruza-healthcheck-alert
```

Состояние сохраняется только после успешной отправки, поэтому при сбое Telegram алерт
повторится на следующем прогоне. Это внутренний мониторинг на том же VPS; внешний
uptime monitor (если VPS целиком недоступен) — **OPEN**.

### Rollback drill

Dry-run rollback plan:

**[Linux]**
```bash
cd /opt/icebeach
bash scripts/server/rollback-api.sh --target-tag "v1.0.0-rc.<previous>"
```

Evidence 2026-10-07 MSK: dry-run на prod `--target-tag "v1.0.0-rc.19"` →
`ROLLBACK_PLAN_OK target=v1.0.0-rc.19`. `--execute` **не запускался** — только с Owner GO.

Execute rollback only after dry-run is clean:

```bash
bash scripts/server/rollback-api.sh \
  --target-tag "v1.0.0-rc.<previous>" \
  --deploy-command "docker compose --env-file .env.docker up --build -d" \
  --healthcheck-command "bash scripts/server/healthcheck.sh --api-url https://dashboard.example.com/api --dashboard-url https://dashboard.example.com --log-file /var/log/ruza/healthcheck.log" \
  --execute
```

### Остановка

**[Linux]**
```bash
cd /opt/icebeach && docker compose down
```

---

## 5. Smoke / preflight на сервере

После login (через dashboard или curl с cookie). `smoke/run` меняет данные,
поэтому выполняйте его только на staging с тестовыми записями:

**[Linux]**
```bash
API=https://dashboard.example.com/api
DATE=2026-06-10

curl -sS "$API/health"
# С сессией admin (cookie из браузера):
curl -sS "$API/preflight/summary?date=$DATE" -H "Cookie: icebeach_session=..."
curl -sS -X POST "$API/smoke/run?date=$DATE" -H "Cookie: icebeach_session=..."
```

Локально с Windows (если API проброшен):

**[PowerShell]**
```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\smoke-local.ps1 -Date "2026-06-10"
```

Для удалённого HTTPS staging используйте `scripts/staging-proof.ps1` с
`-ApiBaseUrl "https://dashboard.example.com/api"` и `-DashboardUrl "https://dashboard.example.com"`.

Prod proof (evidence 2026-10-07 MSK: `SUMMARY blockers=0`):

**[PowerShell]**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\staging-proof.ps1 `
  -ApiBaseUrl "https://ruza.mywavewake.ru/api" `
  -DashboardUrl "https://ruza.mywavewake.ru" `
  -Date "2026-09-30"   # любая дата внутри сезона
# ручная проверка с Windows: schannel без доступа к CRL/OCSP падает — нужен --ssl-no-revoke
curl.exe --ssl-no-revoke -sS https://ruza.mywavewake.ru/api/health
```

Если включён Xray VPN, запросы к prod давали TLS timeouts — выключить VPN или
добавить домен в обход и повторить.

Preflight: даты вне сезона (`06-01..10-01`, захардкожено) дают blocker availability by design;
для proof выбирайте дату внутри сезона (evidence: `2026-09-30` → `blockers=0`).

### Restore backup (только в отдельную таблицу)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore-sheets-backup.ps1 -BackupDir .\backups\sheets\<timestamp>
powershell -ExecutionPolicy Bypass -File .\scripts\restore-sheets-backup.ps1 -BackupDir .\backups\sheets\<timestamp> `
  -Write -TargetSpreadsheetId "<id_отдельной_тестовой_таблицы>"
```

`--write` отказывает (exit 2, `RESTORE_REFUSED`), если target пустой или совпадает с
`SPREADSHEET_ID` / `INTAKE_SPREADSHEET_ID`. Disaster recovery в prod — только с Owner GO:
`-AllowProdTarget` + ввод `OVERWRITE SPREADSHEET_ID` (или `OVERWRITE INTAKE_SPREADSHEET_ID`)
в интерактивном терминале. Evidence 2026-10-07: restore-write в отдельную тестовую таблицу,
15/15 вкладок совпали по строкам и значениям.

---

## 6. Чеклист GO / NO-GO

**GO:**
- `https://dashboard.example.com/api/health` → `{"status":"ok"}`
- preflight blockers = 0
- smoke ok = true
- login + KPI + bookings на staging dashboard

**NO-GO:**
- 502 на Sheets (проверить `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` и доступ SA к spreadsheet)
- CORS errors (точный origin в `CORS_ALLOW_ORIGINS`)
- cookies не ставятся (`SESSION_COOKIE_SECURE=true` только на HTTPS)

---

## 7. Быстрые ссылки

- [STAGING_DEPLOY.md](STAGING_DEPLOY.md)
- [23_STAGING_LAUNCH_CHECKLIST.md](../icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md)
- [SECURITY.md](SECURITY.md)
