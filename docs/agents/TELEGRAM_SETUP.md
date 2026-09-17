# Telegram для Ops Alert и Daily Brief

## 1. Создать бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. `/newbot` → имя и username бота.
3. Сохраните **token** (вида `123456:ABC...`).

## 2. Узнать chat_id owner

1. Напишите боту любое сообщение.
2. Откройте в браузере: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Найдите `"chat":{"id":123456789` — это **TELEGRAM_OWNER_CHAT_ID**.

## 3. Добавить в `.env` (корень Ruza)

```env
AGENTS_SECRET=change-me-long-random-string
AGENTS_API_BASE=http://127.0.0.1:8000
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_OWNER_CHAT_ID=your-chat-id
PUBLIC_CLUB_ID=ice_beach_ruza
```

Перезапустите API: **[PowerShell]** `.\scripts\docker-up.ps1 -Dev`

## 4. Проверка

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\run-agent.ps1 -Agent daily_brief -Mode morning
Get-Content logs\agents.log -Tail 5
```

Если token задан — сообщение придёт в Telegram и в `logs/agents.log`.

## 5. Расписание (опционально)

```powershell
.\scripts\schedule-agents.ps1
```

Отключить: `.\scripts\schedule-agents.ps1 -Unregister`
