# MyWave Infrastructure Canon

Статус: базовая master-карта до следующего подтвержденного инфраструктурного
аудита. Если фактическое состояние расходится с этой картой, расхождение
фиксируется и согласуется до изменения runtime или документации.

## Серверы

| Server | Canonical name | Provider / IP | Capacity | Назначение |
|---|---|---|---|---|
| S1 | `mywave-bot-server` | Timeweb Cloud / `62.113.42.227` | 2 CPU / 4 GB RAM / 50 GB NVMe | MyWave Core + Bots/Content + AI + Event App staging |
| S2 | `MyWavetour` | Timeweb Cloud / `5.129.249.113` | 2 CPU / 2 GB RAM / 40 GB NVMe | MyWave Tourism production |
| S3 | `Friendly Cygnus` | Timeweb Cloud / `72.56.99.214` | 1 CPU / 1 GB RAM / 15 GB NVMe | Shared EU / LLM / Proxy infrastructure |

### S1 — mywave-bot-server

- MyWave Site: production, `/var/www/mywave`, `mywavewake.ru`.
- Telegram Bot MyWave: `/opt/mywave-bot`.
- ParserNews: `/opt/bot3/parser-new-bot`.
- AI Team: `/opt/mywave/ai-team`, `agm.mywavewake.ru`.
- Event / Champ App: STAGING, `/var/www/mywave-event-app`; не production.
- Nginx и Redis: инфраструктурные сервисы.
- PilatesReformerTGbot физически расположен на S1, но не относится к MyWave Core.

### S2 — MyWavetour

Отдельный production-контур MyWave Tourism: Web, Admin, API, PostgreSQL 16,
reverse proxy и EU-egress bridges. Каноническое имя проекта — `tourism`.
`toutism` является legacy/ошибочным именованием и не используется для новых
файлов, сервисов и документации.

### S3 — Friendly Cygnus

Shared EU / LLM Gateway: LiteLLM, 3proxy/SOCKS5, Tourism relay, Cloudflared,
tunnel-only SSH и monitoring. Размещать на S3 сайты, пользовательские приложения
или новые продукты запрещено.

## Типы сущностей

- Продукты: Site/Core, Event App, Tourism, Spot Map, Online Coaching,
  Club Box/Ruza CRM, Sponsor Platform.
- Общие платформенные сервисы: Athlete/Client ID, Knowledge Base, Media Archive,
  ParserNews, AI Team.
- Инфраструктура: VPS, Docker, Nginx, PostgreSQL, Redis, LiteLLM,
  proxy/tunnels, monitoring, backups.

Wake Challenge, Wake Surf Safari, Freeride Hotel, SnowPolia и другие
бизнес-проекты не становятся отдельными server applications автоматически.
Самостоятельный deployment создается только при доказанной необходимости.

## Обязательная deployment-карточка

Каждый компонент описывается одной строкой:

`Product → Environment → Server → Canonical Folder → GitHub Repository → Domain/API → Database/Backup`

Новый VPS, Docker Compose project, база данных или верхнеуровневый каталог не
создается только из-за появления функции. Сначала компонент классифицируется как
новый продукт, модуль существующего продукта или общий платформенный сервис.

## Ruza deployment record

`Club Box/Ruza CRM → NOT DEPLOYED → TBD → TBD → YaroslavValeev/Ruza → TBD → Google Sheets / backup policy TBD`

На S1 подтверждено отсутствие `/opt/icebeach`; этот путь не является
каноническим. S1 уже является shared production/staging host, поэтому размещение
Ruza, canonical folder, домен/API, data source и backup должны быть согласованы
до создания каталога, Compose project, nginx vhost или cron job.

## Короткая формула

- S1 = MyWave Core + Bots/Content + AI + Event App staging.
- S2 = MyWave Tourism production.
- S3 = EU / LLM / Proxy infrastructure.
