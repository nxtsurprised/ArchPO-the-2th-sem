# Observability в системе ГОСТ 34

## Обзор

Три столпа observability реализованы для всех микросервисов:

| Столп | Инструмент | Доступ |
|-------|-----------|--------|
| **Метрики** | Prometheus + Grafana | http://localhost:9090, http://localhost:3001 |
| **Логи** | Loki + Promtail + Grafana | http://localhost:3001 (раздел Explore) |
| **Трейсинг** | — | Запланировано в v2 (OpenTelemetry + Jaeger) |

Correlation ID (`X-Request-ID`) пробрасывается через nginx → все сервисы → structlog.
Это позволяет связать логи одного запроса без полного трейсинга.

---

## Метрики (Prometheus)

### Сбор

Prometheus скрейпит `/metrics` каждые 15 секунд:

| Job | Target | Что собирает |
|-----|--------|-------------|
| `auth-service` | `auth-service:8001/metrics` | HTTP latency, request count, error rate |
| `catalog-service` | `catalog-service:8002/metrics` | HTTP latency, request count, error rate |
| `generation-service` | `generation-service:8003/metrics` | HTTP latency, request count, error rate |
| `workflow-service` | `workflow-service:8004/metrics` | HTTP latency, request count, error rate |
| `pmi-agent` | `pmi-agent:8006/metrics` | PMI-специфичные метрики + HTTP |
| `prometheus` | `localhost:9090` | Self-monitoring |

### Инструментация

Все сервисы используют `prometheus-fastapi-instrumentator`:

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(app)
```

Автоматически предоставляет:

```
http_requests_total{method, handler, status}            — счётчик запросов
http_request_duration_seconds{method, handler, le}      — гистограмма латентности
http_request_size_bytes{method, handler}                 — размер запроса
http_response_size_bytes{method, handler}                — размер ответа
```

### Полезные запросы (PromQL)

```promql
# Request rate по сервисам
sum by (job) (rate(http_requests_total[1m]))

# P95 latency
histogram_quantile(0.95, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m])))

# Доля 5xx ошибок
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Сервисы недоступны
up{job=~"auth-service|catalog-service|generation-service|workflow-service"} == 0
```

---

## Алерты

Файл: `observability/alert_rules.yml`

| Алерт | Условие | Severity |
|-------|---------|---------|
| `ServiceDown` | `up == 0` дольше 1 мин | critical |
| `HighHttpLatency` | P95 > 2s дольше 3 мин | warning |
| `HighErrorRate` | 5xx > 5% дольше 2 мин | warning |
| `KafkaConsumerLag` | consumer lag > 100 дольше 5 мин | warning |

---

## Логи (Loki + Promtail)

### Сбор

Promtail читает Docker-логи через `/var/run/docker.sock` и парсит JSON-формат structlog:

```yaml
# Контейнеры под наблюдением:
- auth-service
- catalog-service
- generation-service
- workflow-service
- pmi-agent
- nginx
```

Метки после парсинга: `container`, `service`, `level`, `event`.

### Формат логов

Все сервисы используют structlog в JSON-формате:

```json
{
  "timestamp": "2026-04-11T12:00:00Z",
  "level": "info",
  "event": "document_archived",
  "document_id": "uuid",
  "archive_key": "projects/.../docs/.../job.docx",
  "service": "generation-service",
  "request_id": "uuid"
}
```

### Запросы в Grafana (LogQL)

```logql
# Все логи одного сервиса
{service="auth-service"}

# Только ошибки
{service=~"auth-service|catalog-service"} | json | level = "error"

# Трейсинг запроса по correlation_id
{service=~".+"} | json | request_id = "uuid-here"

# События архивирования
{service="generation-service"} | json | event = "document_archived"
```

---

## Grafana

**URL:** http://localhost:3001  
**Логин:** `admin` / `admin` (по умолчанию, меняется через `GRAFANA_USER` / `GRAFANA_PASSWORD`)

### Автоматически provisioned

| Что | Файл |
|-----|------|
| Datasource: Prometheus | `observability/grafana/provisioning/datasources/datasources.yml` |
| Datasource: Loki | там же |
| Dashboard: GOST 34 — Services Overview | `observability/grafana/provisioning/dashboards/services-overview.json` |

### Dashboard "GOST 34 — Services Overview"

Панели:
- **Service Uptime** — статус всех сервисов (UP/DOWN)
- **HTTP Request Rate** — запросы/сек по сервисам
- **HTTP P95 Latency** — 95-й перцентиль латентности
- **HTTP 5xx Error Rate** — ошибки сервера
- **HTTP 4xx Error Rate** — ошибки клиента
- **Logs** — live-лог из Loki для всех сервисов

---

## Структура файлов

```
observability/
  prometheus.yml              # scrape_configs для всех сервисов
  alert_rules.yml             # правила алертов
  loki-config.yml             # конфигурация Loki (filesystem storage)
  promtail-config.yml         # сбор Docker-логов + парсинг structlog JSON
  grafana/
    provisioning/
      datasources/
        datasources.yml       # Prometheus + Loki datasources
      dashboards/
        dashboards.yml        # путь к папке с JSON дашбордами
        services-overview.json
```

---

## Расширение в v2

| Что добавить | Зачем |
|---|---|
| OpenTelemetry + Jaeger | Распределённый трейсинг: видеть полный путь запроса через все сервисы |
| Kafka JMX exporter | Метрики Kafka: consumer lag, throughput, partition offset |
| Postgres exporter | Метрики PostgreSQL: connections, query duration, lock waits |
| MongoDB exporter | Метрики MongoDB: операции, индексы, replication lag |
| Alertmanager | Отправка алертов в Slack / Telegram / email |
| SLO/SLA дашборды | Error budget, uptime за 30 дней |
