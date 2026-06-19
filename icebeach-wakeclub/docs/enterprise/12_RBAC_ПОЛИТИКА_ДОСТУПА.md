# RBAC политика доступа (v1)

- admin: всё
- operator: bookings/clients/checkins
- pilot: очередь + статусы
- coach: свои сессии + заметки
- marketing_read: read-only KPI/marketing

UI не защита — enforce на backend. Всё в audit_log.
