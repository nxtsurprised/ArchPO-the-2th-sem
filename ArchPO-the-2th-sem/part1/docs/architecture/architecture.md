# Архитектура системы

## Общая схема

```
┌──────────────────────────────────────────────────────┐
│                 Frontend (React SPA)                  │
└─────────────────────────┬────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────┐
│     nginx (API Gateway, Rate Limiter, CORS)           │
│  5 зон rate limiting: login/write_api/generation/     │
│  pmi/global_api  •  /internal/* → BLOCKED            │
└──┬──────────┬───────────┬──────────────┬─────────────┘
   │          │           │              │
┌──▼──┐  ┌───▼───┐  ┌────▼────┐  ┌──────▼──────┐
│Auth │  │Catalog│  │Generati-│  │  Workflow   │
│:8001│  │ :8002 │  │on :8003 │  │    :8004    │
└──┬──┘  └───┬───┘  └────┬────┘  └──────┬──────┘
   │    ▲    │  ▲    ▲   │  ▲           │
   │    │Kafka│  │    │   │  │     Kafka events
   │  PgSQL  │MongoDB│  MinIO  │       │
   │         │       │hot+cold │     PgSQL
   │         │       │         │
   │    ┌────▼───────▼─────────▼────┐
   │    │     Kafka (KRaft)  :9092  │
   │    │     Kafka UI       :9080  │
   │    └───────────────────────────┘
   │
   ├──────────────────────────────────────────────┐
   │         Redis :6379 (кеш + rate limiting)    │
   └──────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│               Observability Stack                    │
│  Prometheus :9090  Grafana :3001  Loki :3100        │
│  Promtail (сборщик Docker-логов)                    │
└─────────────────────────────────────────────────────┘
```

## Межсервисные коммуникации

### Синхронный REST

| Откуда | Куда | Эндпоинт | Зачем |
|--------|------|----------|-------|
| Generation (JWTAuth) | Auth | `/.well-known/jwks.json` | Публичный ключ RS256 (кеш в Redis, TTL 1 час) |
| Workflow | Auth | `/internal/users/:id/permissions` | Проверка права на согласование |
| Workflow | Auth | `/internal/users/batch` | ФИО участников для отображения |
| Auth (unified audit) | Catalog, Workflow, Generation | `/internal/audit` | Агрегация аудит-логов для суперадмина |
| Generation | Catalog | `/internal/documents/:id/render-bundle` | Все данные для генерации одним запросом |
| Generation (archive) | Catalog | `/internal/documents/archivable` | Список документов для архивирования |
| Generation (archive) | Catalog | `/internal/documents/:id/archive` | Пометить документ архивированным |

### Асинхронный Kafka (топик `gost34.workflow.events`)

| Producer | Consumer | Событие | Действие |
|----------|----------|---------|---------|
| Workflow | Catalog | `approval.submitted` | Информирование об отправке на согласование |
| Workflow | Catalog | `approval.completed` | Информирование о завершении раунда |
| Workflow | Catalog | `approval.cancelled` | Информирование об отмене |
| Workflow | Catalog | `document.locked` | `Document.locked=True`, `status="pending"` в MongoDB |
| Workflow | Catalog | `document.unlocked` | `Document.locked=False`, `status="draft"\|"rejected"` в MongoDB |

Подробнее: [kafka-eda.md](kafka-eda.md)

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

## Инфраструктурные компоненты

| Компонент | Образ | Порт | Назначение |
|-----------|-------|------|-----------|
| nginx | nginx:1.25-alpine | 8080 | API Gateway, Rate Limiter, CORS, статика |
| Kafka | confluentinc/cp-kafka:7.6.1 | 9092 | Асинхронный обмен событиями (KRaft) |
| Kafka UI | provectuslabs/kafka-ui | 9080 | Мониторинг топиков и consumer lag |
| MinIO | minio/minio | 9000/9001 | Объектное хранилище (hot + archive buckets) |
| Redis | redis:7.2-alpine | 6379 | Кеш (JWKS, сессии) + счётчики rate limiting |
| Prometheus | prom/prometheus:v2.50.1 | 9090 | Сбор метрик со всех сервисов |
| Grafana | grafana/grafana:10.3.3 | 3001 | Дашборды и алерты |
| Loki | grafana/loki:2.9.5 | 3100 | Агрегация структурированных логов |
| Promtail | grafana/promtail:2.9.5 | — | Сбор Docker-логов → Loki |

## Хранилище документов (MinIO)

| Bucket | Тип | Назначение |
|--------|-----|-----------|
| `documents` | Hot | Активные генерируемые .docx/.xlsx |
| `documents-archive` | Cold | Завершённые документы старше 90 дней |
| `templates` | Hot | .dotx шаблоны ГОСТ 2.105 |

Архивирование: фоновый воркер в generation-service (каждые 24 часа) переносит документы со статусом `approved`/`rejected` старше `ARCHIVE_AFTER_DAYS` из `documents` в `documents-archive`. Подробнее: [cold-storage раздел в generation-service-spec.md](generation-service-spec.md).

## Rate Limiting (nginx)

| Зона | Лимит | Endpoint |
|------|-------|---------|
| `login` | 20 req/min | `/api/auth/login`, `/api/auth/password/reset-request` |
| `write_api` | 60 req/min | `/api/auth/*`, `/api/catalog/*`, `/api/workflow/*` |
| `generation` | 10 req/min | `/api/generation/*` |
| `pmi` | 5 req/min | `/api/pmi/*` |
| `global_api` | 300 req/min | Весь API (последний рубеж) |

Ответ при превышении: HTTP 429. Дополнительно: slowapi (Python) на `/api/auth/login` с Redis-счётчиком.

## Что запланировано на v2

| Компонент | Текущее состояние | Что улучшить |
|-----------|-------------------|-------------|
| Audit Service | Internal API агрегация | Отдельный Audit Service + Elasticsearch |
| JWT blacklist | Только DB-сессии (refresh) | Redis blacklist для access-токенов |
| Kafka Schema Registry | Нет валидации схемы | Confluent Schema Registry + DLQ |
| MinIO tiering | Два bucket вручную | S3 lifecycle policies |
| Масштабирование | По одному инстансу | nginx upstream + несколько реплик |
