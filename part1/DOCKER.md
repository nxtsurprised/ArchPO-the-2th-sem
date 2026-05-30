# Docker — памятка по работе с системой

## Сервисы и порты

| Сервис | Порт | Что это |
|--------|------|---------|
| nginx | 8081 / 8444 | API Gateway + Frontend |
| auth-service | 8001 | Аутентификация |
| catalog-service | 8002 | Шаблоны, функции, документы |
| generation-service | 8003 | Генерация .docx/.xlsx |
| workflow-service | 8004 | Согласование |
| /api/pmi/* | — | Заглушка ПМИ в nginx |
| auth-postgres | — | PostgreSQL для auth (внутренний) |
| workflow-postgres | — | PostgreSQL для workflow (внутренний) |
| catalog-mongodb | — | MongoDB для catalog (внутренний) |
| minio | 9000 / 9001 | Файловое хранилище / Консоль |
| redis | 6379 | Кеш и rate limiter |
| kafka | — | Очередь событий (внутренний) |
| kafka-ui | 9080 | Веб-интерфейс Kafka |
| prometheus | 90
| alertmanager | 9093 | Алерты |
| grafana | 3001 | Дашборды |
| loki | 3100 | Агрегация логов |

---

## Основные команды

### Запуск и остановка

```bash
# Собрать и запустить систему
bash scripts/build.sh -t coursework
bash scripts/deploy.sh -t coursework

# Остановить всё (контейнеры + сети, данные сохраняются)
bash scripts/stop.sh -t coursework

# Остановить и удалить все данные (volumes)
docker compose down -v
```

### Пересборка конкретного сервиса

```bash
# Пересобрать и перезапустить один сервис
docker compose up -d --build --force-recreate catalog-service

# Перезапустить без пересборки (например, после правки nginx.conf)
docker compose restart nginx

# Пересоздать контейнер (новые volume-маунты или env-переменные)
docker compose up -d --force-recreate prometheus
```

### Статус

```bash
# Список контейнеров с портами и статусом
docker compose ps

# Только упавшие
docker compose ps | grep -v "Up\|healthy"
```

---

## Логи

```bash
# Логи одного сервиса (последние 100 строк)
docker compose logs --tail=100 catalog-service

# Следить в реальном времени
docker compose logs -f catalog-service

# Несколько сервисов сразу
docker compose logs -f auth-service catalog-service

# Все сервисы с временными метками
docker compose logs -t --tail=50
```

---

## Отладка

```bash
# Зайти в контейнер
docker exec -it part1-catalog-service-1 bash

# Посмотреть переменные окружения сервиса
docker exec part1-auth-service-1 env

# Проверить health-статус
docker inspect --format='{{.State.Health.Status}}' part1-catalog-service-1

# Посмотреть кто занимает порт
docker ps | grep 9090
```

---

## Частые ситуации

### Порт уже занят
```bash
# Найти контейнер на порту
docker ps | grep 9093

# Остановить и удалить его
docker stop <name> && docker rm <name>
```

### Контейнер не пересобирается после `up --build`
```bash
# Нужен force-recreate
docker compose up -d --build --force-recreate <service>
```

### nginx не подхватил новый конфиг
```bash
# Достаточно restart, rebuild не нужен
docker compose restart nginx
```

### Очистить кеш сборки (если образ не обновляется)
```bash
docker compose build --no-cache <service>
docker compose up -d --force-recreate <service>
```

---

## Observability

```bash
# Prometheus — метрики и алерты
open http://localhost:9090/alerts    # активные алерты
open http://localhost:9090/targets   # статус scrape (UP/DOWN)

# Grafana — дашборды и логи
open http://localhost:3001           # admin / admin

# Alertmanager — активные уведомления
open http://localhost:9093

# Kafka UI
open http://localhost:9080

# MinIO консоль
open http://localhost:9001           # minioadmin / minioadmin_change_me
```

### Запрос логов через Loki (в Grafana Explore)
```logql
# Все логи nginx
{service="nginx"}

# Только ошибки
{service="nginx"} |= " 503 "

# По любому сервису
{service="catalog-service"}
```

---

## Compose-файл

| Файл | Когда использовать |
|------|-------------------|
| `docker-compose.yml` | Основной учебный стенд без тяжелого PMI-agent |
