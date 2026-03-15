# Архитектура системы

## Общая схема

```
┌──────────────────────────────────────────────────────┐
│                 Frontend (React SPA)                  │
└─────────────────────────┬────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────┐
│          nginx (API Gateway, TLS, CORS)               │
│   /api/auth/*  /api/catalog/*  /api/gen/*  /api/wf/*  │
│   /internal/* → BLOCKED                               │
└──┬──────────┬───────────┬──────────────┬─────────────┘
   │          │           │              │
┌──▼──┐  ┌───▼───┐  ┌────▼────┐  ┌──────▼──────┐
│Auth │  │Catalog│  │Generati-│  │  Workflow   │
│Svc  │  │  Svc  │  │on Svc   │  │    Svc      │
│:8001│  │ :8002 │  │  :8003  │  │   :8004     │
└──┬──┘  └───┬───┘  └────┬────┘  └──────┬──────┘
   │         │           │              │
┌──▼──┐  ┌───▼───┐  ┌────▼────┐  ┌──────▼──────┐
│PgSQL│  │MongoDB│  │  MinIO  │  │   PgSQL     │
│auth │  │catalog│  │  files  │  │  workflow   │
└─────┘  └───────┘  └─────────┘  └─────────────┘
```

## Межсервисные коммуникации

Все вызовы — синхронный REST (в v2 часть заменится на Kafka events).

| Откуда | Куда | Эндпоинт | Зачем |
|--------|------|----------|-------|
| Catalog, Generation, Workflow | Auth | `/.well-known/jwks.json` | Публичный ключ для верификации JWT (кеш 1 час) |
| Workflow | Auth | `/internal/users/:id/permissions` | Проверка права на согласование |
| Workflow | Auth | `/internal/users/batch` | ФИО участников для отображения |
| Auth (unified audit) | Catalog, Workflow, Generation | `/internal/audit` | Агрегация аудит-логов для суперадмина |
| Generation | Catalog | `/internal/documents/:id/render-bundle` | Все данные для генерации одним запросом |
| Catalog | Workflow | `/internal/documents/:id/status` | Проверка блокировки перед редактированием |

### Защита internal API

Маршруты `/internal/*` не проксируются nginx наружу. Внутри Docker-сети сервисы обращаются напрямую: `http://auth-service:8001/internal/...`. Дополнительная защита — заголовок `X-Internal-Secret` (общий секрет из env).

## Мультипроектная модель

Организация не имеет фиксированной стороны (customer/contractor). Сторона определяется контекстом проекта:

```
organizations (нейтральные)
    │
    ├── projects.customer_org_id → "заказчик в этом проекте"
    └── projects.contractor_org_id → "подрядчик в этом проекте"
```

Одна организация может участвовать в нескольких проектах. Один пользователь может иметь разные роли в разных проектах.

JWT payload содержит массив ролей с вычисленной стороной:
```json
{
  "sub": "user-uuid",
  "org_id": "org-uuid",
  "roles": [
    { "project_id": "proj-1", "role": "pm", "side": "customer" },
    { "project_id": "proj-2", "role": "analyst", "side": "customer" }
  ]
}
```

## Аудит

Каждый сервис ведёт локальный audit_log с единой структурой (через shared AuditLogger). Запись атомарна с бизнес-операцией (одна транзакция). Auth агрегирует логи всех сервисов через internal API для интерфейса суперадмина.

Единая модель записи:
```
timestamp, user_id, user_side, user_role, ip_address, user_agent,
service, action, resource_type, resource_id, project_id,
correlation_id, result, changes (JSON diff), details
```

## Стандарты и нормативная база

| Документ | Что регулирует |
|----------|---------------|
| ГОСТ 34.602-2020 | Структура ТЗ (обязательные разделы) |
| ГОСТ 34.603-92 | Структура ПМИ |
| ГОСТ 2.105-2019 | Форматирование документов (шрифт, поля, заголовки) |
| 44-ФЗ + Минфин | Структура НМЦК |
| Приказ ФСТЭК №17 | Меры защиты ГИС (ИАФ, УПД, РСБ, ЗИС, ОЦЛ) |
| ISO/IEC 27001:2022 | Управление ИБ |
| 152-ФЗ | Персональные данные |
| ГОСТ Р 58256-2018 | Идентификация и аутентификация |
| ПП-1119 | Уровни защищённости ПДн (УЗ-4) |

## Подготовка к v2

В MVP заложены интерфейсы-заглушки для компонентов v2:

| Компонент v2 | Заглушка в MVP | Интерфейс |
|-------------|----------------|-----------|
| Kafka (EDA) | structlog.info() | EventEmitter.emit(name, payload) |
| Redis | dict с TTL | CacheService.get()/set() |
| Audit Service (Elasticsearch) | Internal API агрегация | AuditLogger.log() |
| Notifications | — | Events: approval.submitted, approval.completed |
| Rate Limiter | nginx limit_req | — |
| Observability | structlog JSON | Correlation ID в каждом логе |

Переход: замена одной реализации интерфейса, не рефакторинг бизнес-кода.
