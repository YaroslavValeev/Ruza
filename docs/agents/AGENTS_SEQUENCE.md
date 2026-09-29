# Порядок внедрения Agents

```mermaid
flowchart LR
  P0[Docs + smoke] --> P1[Shift UI]
  P1 --> G1{Field test}
  G1 --> P2[Agents infra]
  P2 --> P3[Runners + QueueCoach]
  P3 --> G2{Telegram env}
  G2 --> P4[Voice wizard]
  G2 --> P5[Marketing backlog]
```

## Фазы

| # | Фаза | Rollback point |
|---|------|----------------|
| 0 | Документация | удалить docs/agents |
| 1 | `/shift/today` + UI | откат route + page |
| 2 | `apps/agents` + internal API | отключить scripts |
| 3 | Runners по расписанию | `-Unregister` scheduler |
| 4 | Voice wizard | скрыть кнопку в UI |
| 5 | LTV, approve, `/book` | feature flags |

## Зависимости

- LateMarker требует `AGENTS_SECRET` и работающий API
- DailyBrief требует KPI + bookings endpoints
- Telegram опционален — fallback `logs/agents.log`

## Ручной контроль владельца

1. Полевой тест после фазы 1
2. Telegram credentials после фазы 2
3. Подтверждение времени brief после фазы 3
