# Troubleshooting

## Нет доступа к Sheets (`UNAUTHORIZED`, permission)

- Проверь, что service-account email добавлен в доступы таблицы (Editor).
- Проверь `SPREADSHEET_ID` и путь `GOOGLE_SERVICE_ACCOUNT_JSON`.

## `TAB_MISSING` / `COLUMN_MISSING`

- Сравни вкладки/заголовки с PRO v1.
- Исправь имя вкладки и заголовки (регистр/опечатки).

## CORS

- Проверь `CORS_ALLOW_ORIGINS` в `.env`.
- Dashboard origin должен быть в allowlist.

## `Session expired` / `Invalid token`

- Перелогинься.
- Проверь `API_SESSION_SECRET` и системное время.

## `SLOT_FULL`

- Слот занят по capacity.
- Выбрать другой slot/boat/date.

## `BOOKING_NOT_FOUND`

- Обновить список дня.
- Проверить корректность `booking_id`.
