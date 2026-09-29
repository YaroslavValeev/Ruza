# Установка на телефоны без App Store / Google Play

Для пилота и owner достаточно **PWA** (веб-приложение с ярлыком на домашнем экране). Store не нужен.

## 1. Запуск на ПК

**[PowerShell]**

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\docker-up.ps1 -Dev
.\scripts\mobile-lan-url.ps1
```

Телефон и ПК должны быть в **одной Wi‑Fi сети**.

## 2. Ссылки для двух телефонов

Скрипт `mobile-lan-url.ps1` покажет адреса вида:

| Роль   | URL |
|--------|-----|
| Пилот  | `http://192.168.x.x:5173/m/pilot` |
| Owner  | `http://192.168.x.x:5173/m/owner` |
| Справка | `http://192.168.x.x:5173/m/install` |

Вход: `/login?next=/m/pilot` или `/login?next=/m/owner` — после кода попадёте сразу в нужный экран.

## 3. iPhone (owner / пилот)

1. Откройте ссылку в **Safari** (не во встроенном браузере Telegram).
2. Войдите по `staff_user_id` + телефон + код.
3. **Поделиться** → **На экран «Домой»**.
4. Запускайте иконку **Ice Beach** как отдельное приложение.

> Без Apple Developer аккаунта **.ipa не собрать** для sideload. PWA — стандартный путь для 1–2 устройств.

## 4. Android

### Вариант A — PWA (рекомендуется)

1. Chrome → открыть ссылку пилота или owner.
2. Войти.
3. Меню → **Установить приложение** / **Добавить на главный экран**.

### Вариант B — debug APK (опционально)

**[PowerShell]**

```powershell
cd "F:\Проекты MyWave\NEW2026\Ruza"
.\scripts\build-android-apk.ps1
```

Готовый файл:

`icebeach-wakeclub\apps\dashboard\android\app\build\outputs\apk\debug\app-debug.apk`

Передайте APK пилоту (USB, Telegram, Google Drive). На телефоне включите «Установка из неизвестных источников» для Chrome/Files.

**Важно:** в APK зашит URL API с LAN IP вашего ПК. Если IP сменится — пересоберите APK или используйте PWA по URL.

## 5. Роли

| Экран | Роли |
|-------|------|
| `/m/pilot` | pilot, admin, operator |
| `/m/owner` | admin, operator |

## 6. Проверка

**[PowerShell]**

```powershell
.\scripts\docker-status.ps1 -Dev
.\scripts\smoke-local.ps1
```

Если на телефоне **«API недоступно»**, а страница открывается:

1. Телефон и ПК в **одной Wi‑Fi** (не мобильный интернет).
2. **[PowerShell] (администратор)** откройте порт dashboard:
   ```powershell
   .\scripts\open-lan-firewall.ps1
   ```
3. Перезапустите dev-стек (API идёт через прокси `/api` на том же :5173):
   ```powershell
   .\scripts\docker-up.ps1 -Dev
   ```
4. Проверка:
   ```powershell
   .\scripts\mobile-preflight.ps1
   ```

На экране логина внизу должен быть API вида `http://192.168.x.x:5173/api`, не `:8000`.

## Файлы

- `icebeach-wakeclub/apps/dashboard/public/manifest.webmanifest`
- `icebeach-wakeclub/apps/dashboard/public/sw.js`
- `icebeach-wakeclub/apps/dashboard/src/mobile/*`
- `scripts/mobile-lan-url.ps1`
- `scripts/build-android-apk.ps1`
