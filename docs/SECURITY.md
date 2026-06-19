# Security (MVP)

- Sheets-only (без БД).
- Secrets в `.env` / `.env.docker` (не коммитить).
- `service-account.json` только локально в `secrets/` или через env base64.
- Face/Voice — только по согласию (`consent_face`, `consent_voice` в clients).
- В Sheets не храним фото/аудио/видео.
- Push blocked by default (git hooks).
- **Ротация:** если секреты попали в git history (`1.txt`, `2.txt`) — отозвать и перевыпустить Telegram token, Google OAuth, Cursor API key.
- **Google Sheets SSL:** при `SSL: WRONG_VERSION_NUMBER` установить `DISABLE_SYSTEM_PROXY_FOR_GOOGLE=true` в `.env`.
