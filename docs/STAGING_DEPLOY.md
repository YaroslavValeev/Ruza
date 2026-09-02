# Timeweb Staging — Operator Runbook

После **2× green smoke** в local Docker:

## 1. Push (оператор)

**[PowerShell]**
```powershell
$env:ALLOW_GIT_PUSH=1; git push -u origin main
```

## 2. Timeweb App Platform

См. [22_TIMEWEB_BACKEND_DEPLOY.md](../icebeach-wakeclub/docs/enterprise/22_TIMEWEB_BACKEND_DEPLOY.md)

- Dockerfile: `icebeach-wakeclub/Dockerfile`
- Port: `8000`
- Health: `/health`
- Env: заполнить `.env.docker` по `.env.docker.example` или перенести те же ключи из
  `apps/api/.env.production.example` в Timeweb App Platform.
- Env gate: `scripts/server/validate-production-env.sh .env.docker` должен пройти без blockers.

## 3. Frontend staging

- Build dashboard с `VITE_API_BASE_URL=https://<staging-api-domain>`
- CORS: добавить staging dashboard origin в `CORS_ALLOW_ORIGINS`

## 4. Checklist GO

Прогнать [23_STAGING_LAUNCH_CHECKLIST.md](../icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md) на staging URL.

Машинная проверка staging/prod URL:

**[PowerShell]**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\staging-proof.ps1 `
  -ApiBaseUrl "https://<staging-api-domain>" `
  -DashboardUrl "https://<staging-dashboard-domain>" `
  -Date "2026-06-01"
```

Если нужно доказать admin-only preflight после входа, передайте cookie сессии:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\staging-proof.ps1 `
  -ApiBaseUrl "https://<staging-api-domain>" `
  -DashboardUrl "https://<staging-dashboard-domain>" `
  -Date "2026-06-01" `
  -SessionCookie "icebeach_session=<cookie>"
```

OTP-запрос скрипт не делает по умолчанию, чтобы случайно не отправлять реальные SMS/Telegram.
Когда side effect разрешен, включите явный probe:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\staging-proof.ps1 `
  -ApiBaseUrl "https://<staging-api-domain>" `
  -DashboardUrl "https://<staging-dashboard-domain>" `
  -ProbeOtpRequest `
  -StaffUserId "<staff_user_id>" `
  -Phone "+7..."
```

На Linux/Timeweb:

```bash
bash scripts/server/staging-proof.sh \
  --api-base-url "https://<staging-api-domain>" \
  --dashboard-url "https://<staging-dashboard-domain>" \
  --date "2026-06-01"
```

## 5. NO-GO

- health красный
- preflight blockers > 0
- smoke failures
- CORS / cookies не работают
