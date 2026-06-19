# 22. Timeweb Backend Deploy

## Цель
Поднять backend `icebeach-wakeclub` в staging на Timeweb Cloud так, чтобы:
- API слушал production-порт внутри контейнера
- `Google Sheets` и `session cookies` работали без локальных костылей
- deploy был воспроизводимым

## Что уже подготовлено в репозитории
- root [`Dockerfile`](/F:/Проекты%20MyWave/NEW2026/Ruza/icebeach-wakeclub/Dockerfile)
- root [`.dockerignore`](/F:/Проекты%20MyWave/NEW2026/Ruza/icebeach-wakeclub/.dockerignore)
- production env template [`apps/api/.env.production.example`](/F:/Проекты%20MyWave/NEW2026/Ruza/icebeach-wakeclub/apps/api/.env.production.example)
- backend config умеет брать Google credentials:
  - из файла
  - из raw JSON env
  - из base64 env

## Рекомендуемый путь сейчас
Для первого staging используем **Timeweb App Platform**, если код лежит в GitHub.
Если нужен полный root-доступ и свой reverse proxy, переходить на VPS позже, после staging smoke.

Официальные ссылки:
- [Timeweb Cloud Apps](https://timeweb.cloud/docs/apps)
- [FastAPI в App Platform](https://timeweb.cloud/docs/apps/deploying-backend-applications/fastapi)

## Что нужно подготовить до деплоя
1. Репозиторий должен быть доступен из GitHub.
2. Нужны значения:
   - `SPREADSHEET_ID`
   - `SESSION_SECRET`
   - Google service account JSON
   - staging frontend origin, например `https://icebeach-dashboard-staging.example`
3. В Google Sheets service account должен иметь доступ к spreadsheet.

## Вариант A: Timeweb App Platform, click-by-click
1. Открой браузер.
2. Перейди в [Timeweb Cloud](https://timeweb.cloud/).
3. Войди в аккаунт.
4. В левом меню открой `Apps`.
5. Нажми `Создать приложение`.
6. Выбери источник `GitHub repository`.
7. Подключи GitHub, если ещё не подключен.
8. Выбери репозиторий с проектом `icebeach-wakeclub`.
9. В настройках сборки укажи, что приложение собирается через `Dockerfile` из корня репозитория.
10. Порт приложения укажи `8000`.
11. В разделе переменных окружения добавь:
    - `APP_ENV=production`
    - `SPREADSHEET_ID=...`
    - `SESSION_SECRET=...`
    - `SESSION_COOKIE_SECURE=true`
    - `ALLOW_LEGACY_STAFF_LOGIN=false`
    - `AUTH_DEBUG_CODE_IN_RESPONSE=false`
    - `DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true`
    - `SHEETS_TAB_CACHE_TTL_SECONDS=15`
    - `CORS_ALLOW_ORIGINS=https://<staging-dashboard-domain>`
12. Передай Google credentials одним из способов:
    - рекомендуется: `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=...`
    - допустимо: `GOOGLE_SERVICE_ACCOUNT_JSON_INLINE={...}`
13. Health endpoint укажи `/health`, если платформа просит путь health-check.
14. Нажми `Deploy`.
15. Дождись статуса `Running`.
16. Открой URL приложения и проверь `/health`.

Ожидаемый результат:
- `https://<app-domain>/health` отвечает `{"status":"ok"}`

## Вариант B: Timeweb VPS / Cloud Server
Использовать, если хочешь полный контроль над логами, reverse proxy, SSL и дальнейшим mobile rollout.

Минимальная схема:
- Ubuntu server
- Docker Engine
- `docker build -t icebeach-api .`
- `docker run --env-file ... -p 8000:8000 icebeach-api`
- reverse proxy на домен

Этот путь лучше для production, но для первого staging медленнее по вводу в эксплуатацию.

## Обязательные production env
Минимум:
- `APP_ENV=production`
- `SPREADSHEET_ID`
- `SESSION_SECRET`
- `SESSION_COOKIE_SECURE=true`
- `CORS_ALLOW_ORIGINS=https://<dashboard-domain>`
- один из:
  - `GOOGLE_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_SERVICE_ACCOUNT_JSON_INLINE`
  - `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`

## Что не делать
- не тащить локальный путь `E:\...\service-account.json` в production env
- не оставлять `AUTH_DEBUG_CODE_IN_RESPONSE=true`
- не ставить wildcard CORS
- не деплоить backend без точного frontend origin

## Проверка после деплоя
1. `GET /health`
2. manual login request-code
3. `preflight` на сезонную дату
4. `smoke` на сезонную дату
5. ручная бронь через staging dashboard

## Definition of Done для backend staging
- deploy воспроизводим через Dockerfile
- secrets подаются через env/secret store
- health-check зелёный
- `preflight` зелёный
- `smoke` зелёный
- API доступен не только локально
