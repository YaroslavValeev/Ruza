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
- Env: `apps/api/.env.production.example`

## 3. Frontend staging

- Build dashboard с `VITE_API_BASE_URL=https://<staging-api-domain>`
- CORS: добавить staging dashboard origin в `CORS_ALLOW_ORIGINS`

## 4. Checklist GO

Прогнать [23_STAGING_LAUNCH_CHECKLIST.md](../icebeach-wakeclub/docs/enterprise/23_STAGING_LAUNCH_CHECKLIST.md) на staging URL.

## 5. NO-GO

- health красный
- preflight blockers > 0
- smoke failures
- CORS / cookies не работают
