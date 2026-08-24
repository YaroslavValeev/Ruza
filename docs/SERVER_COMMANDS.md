# Команды для сервера — Ice Beach / Ruza

Копируй блоки по порядку. Метки: **[PowerShell]** — Windows, **[Linux]** — VPS/Ubuntu.

---

## 0. Что поднять

| Вариант | Когда |
|---------|--------|
| **A. Timeweb App Platform** | Быстрый staging без SSH (GitHub + Dockerfile) |
| **B. VPS + Docker** | Полный контроль, nginx, SSL, API + dashboard |

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
$env:ALLOW_GIT_PUSH=1; git push -u origin main
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
OTP_DELIVERY_WEBHOOK_URL=https://<sms-provider>/send
OTP_DELIVERY_WEBHOOK_TOKEN=<секрет_провайдера>
OTP_DELIVERY_TIMEOUT_SECONDS=8
DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true
SHEETS_TAB_CACHE_TTL_SECONDS=15
CORS_ALLOW_ORIGINS=https://<ваш-dashboard-домен>
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=<из_шага_1.1>
API_HOST=0.0.0.0
API_PORT=8000
```

**Проверка после деплоя [Linux/curl с любой машины]:**
```bash
curl -sS https://<api-domain>/health
curl -sS "https://<api-domain>/preflight/summary?date=2026-06-01" -b "icebeach_session=..." 
# login сначала через dashboard
```

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
git clone https://github.com/<org>/Ruza.git .
# или: git pull origin main  — при обновлении
```

### 3.3 Production env на сервере

**[Linux]**
```bash
cd /opt/icebeach
cp .env.docker.example .env.docker
nano .env.docker
```

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
OTP_DELIVERY_WEBHOOK_URL=https://sms-provider.example/send
OTP_DELIVERY_WEBHOOK_TOKEN=ЗАМЕНИТЕ_НА_СЕКРЕТ_ПРОВАЙДЕРА
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

### 3.4 Запуск API (только backend)

**[Linux]**
```bash
cd /opt/icebeach/icebeach-wakeclub
docker build -t icebeach-api:latest .
docker stop icebeach-api 2>/dev/null; docker rm icebeach-api 2>/dev/null
docker run -d \
  --name icebeach-api \
  --restart unless-stopped \
  --env-file /opt/icebeach/.env.docker \
  -p 127.0.0.1:8000:8000 \
  icebeach-api:latest
```

Проверка:
```bash
curl -sS http://127.0.0.1:8000/health
docker logs -f --tail 100 icebeach-api
```

### 3.5 Запуск API + Dashboard (docker compose)

Перед сборкой dashboard укажите публичный URL API в compose или пересоберите с build-arg.

**[Linux]**
```bash
cd /opt/icebeach
# Отредактируйте docker-compose.yml: VITE_API_BASE_URL=https://api.example.com
docker compose --env-file .env.docker up --build -d
docker compose ps
curl -sS http://127.0.0.1:8000/health
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5173/
```

### 3.6 Nginx + SSL (Let's Encrypt)

**[Linux]**
```bash
apt install -y nginx certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/icebeach <<'NGINX'
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

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

certbot --nginx -d api.example.com -d dashboard.example.com
```

После SSL обновите `CORS_ALLOW_ORIGINS` в `.env.docker` и перезапустите API:
```bash
docker restart icebeach-api
# или: cd /opt/icebeach && docker compose up -d --force-recreate api
```

---

## 4. Обслуживание на сервере

### Обновление кода

**[Linux]**
```bash
cd /opt/icebeach
git pull origin main
cd icebeach-wakeclub
docker build -t icebeach-api:latest .
docker stop icebeach-api && docker rm icebeach-api
docker run -d --name icebeach-api --restart unless-stopped \
  --env-file /opt/icebeach/.env.docker \
  -p 127.0.0.1:8000:8000 \
  icebeach-api:latest
curl -sS http://127.0.0.1:8000/health
```

С compose:
```bash
cd /opt/icebeach
git pull origin main
docker compose --env-file .env.docker up --build -d
```

### Логи и статус

**[Linux]**
```bash
docker ps
docker logs -f --tail 200 icebeach-api
docker compose -f /opt/icebeach/docker-compose.yml logs -f api
```

### Остановка

**[Linux]**
```bash
docker stop icebeach-api
# или
cd /opt/icebeach && docker compose down
```

---

## 5. Smoke / preflight на сервере

После login (через dashboard или curl с cookie):

**[Linux]**
```bash
API=https://api.example.com
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
# Для удалённого API измените $ApiBase в скрипте или:
$env:SMOKE_API_BASE = "https://api.example.com"
```

---

## 6. Чеклист GO / NO-GO

**GO:**
- `/health` → `{"status":"ok"}`
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
