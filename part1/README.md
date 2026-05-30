# ГОСТ 34 Platform: Docker Compose + Loki + Grafana

Коротко: это веб-приложение для работы с документами по ГОСТ 34. В `part1` поднимается frontend, API gateway nginx, auth/catalog/generation/workflow сервисы и инфраструктурные зависимости: PostgreSQL, MongoDB, Redis, Kafka, MinIO.

Кнопка запуска ПМИ в интерфейсе сохранена как заглушка: `/api/pmi/*` возвращает понятный stub-ответ из nginx. Тяжелый `pmi-agent` с Ollama/Playwright/ML-зависимостями не включен в этот Docker Compose вариант, чтобы учебный стенд запускался стабильно.

## Запуск

Требования: Docker, Docker Compose, curl.

```bash
cd part1
bash scripts/build.sh -t v1
bash scripts/deploy.sh -t v1
```

Адреса:

- приложение: http://localhost:8081
- Grafana: http://localhost:3001, логин/пароль `admin` / `admin`
- Loki: http://localhost:3100
- Kafka UI: http://localhost:9080
- MinIO: http://localhost:9001

Остановка:

```bash
cd part1
bash scripts/stop.sh -t v1
```

## Логи в Grafana

В compose уже поднимаются `loki`, `promtail` и `grafana`. Promtail читает Docker-логи контейнеров проекта `part1` и отправляет их в Loki. В Grafana datasource `Loki` добавлен автоматически.

Чтобы быстро создать логи:

```bash
cd part1
bash scripts/generate_logs.sh
```

В Grafana откройте `Explore`, выберите datasource `Loki` и выполните запросы:

```logql
{service="nginx"}
{service="auth-service"}
{service="catalog-service"}
{container=~"part1-.*"}
```

Важно: для задания используются именно логи из Loki, не метрики Prometheus.

## Скриншоты для отчета

Положите изображения в `docs/screenshots/`:

- `app.png` — открытое приложение на http://localhost:8081
- `compose-ps.png` — работающие контейнеры из `docker compose ps`
- `grafana-loki-datasource.png` — datasource Loki в Grafana
- `grafana-logs.png` — результат LogQL-запроса в Grafana Explore

## Multistage

Multistage-сборка описана в Dockerfile для frontend и Python-сервисов с зависимостями: `auth-service`, `catalog-service`, `generation-service`, `workflow-service`.
