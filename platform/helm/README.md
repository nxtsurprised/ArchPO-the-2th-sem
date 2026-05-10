# Helm charts для микросервисов

Этот каталог содержит учебные Helm charts для Kubernetes-деплоя части сервисов из `part1/`.

Сейчас описаны 4 сервиса:

- `auth-service`
- `catalog-service`
- `generation-service`
- `pmi-agent`

Docker Compose из `part1/` не изменяется. Эти charts нужны для Block 5: CI собирает образы, обновляет `image.repository` и `image.tag` в `values.yaml`, а ArgoCD синхронизирует сервисы из Git.

## Структура chart

У каждого сервиса есть:

- `Chart.yaml` - метаданные Helm chart.
- `values.yaml` - настройки образа, ресурсов, проб, HPA и подключений.
- `templates/deployment.yaml` - Kubernetes Deployment.
- `templates/service.yaml` - ClusterIP Service.
- `templates/serviceaccount.yaml` - ServiceAccount.
- `templates/configmap.yaml` - несекретные переменные окружения.
- `templates/secret-env.yaml` - опциональный Secret без реальных значений.
- `templates/hpa.yaml` - HPA, выключен по умолчанию.

## Образы

По умолчанию charts смотрят на локальный registry внутри кластера:

```sh
local-registry.infra.svc.cluster.local:5000/<service-name>:dev
```

CI/CD workflow меняет эти значения на конкретный тег короткого Git SHA.

## Подключения

Настройки внешних зависимостей находятся в блоке `connections` в каждом `values.yaml`.

Используются локальные DNS-имена Kubernetes:

- Kafka: `archpo-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092`
- Redis/Valkey: `redis.databases.svc.cluster.local:6379`
- PostgreSQL: `postgres.databases.svc.cluster.local`
- MongoDB: `mongodb.databases.svc.cluster.local`
- MinIO: `minio.databases.svc.cluster.local:9000`
- Chroma: `chroma.databases.svc.cluster.local:8000`
- Ollama: `ollama.databases.svc.cluster.local:11434`

Реальные пароли и ключи не хранятся в `values.yaml`. Charts ссылаются на существующие Kubernetes Secrets:

- `app-shared-secrets`
- `jwt-secrets`
- `postgres-secret`
- `mongo-secret`
- `redis-secret`
- `minio-secret`

Если секретов нет, Deployment может создаться, но контейнеры не стартуют корректно. Это нормально для локального учебного этапа: секреты создаются базовой инфраструктурой или добавляются отдельно.

## Локальная проверка

Проверить один chart:

```sh
helm lint platform/helm/auth-service
helm template auth-service platform/helm/auth-service --namespace app
```

Проверить все charts:

```sh
platform/cicd/scripts/validate-helm-charts.sh
```

Установить вручную без ArgoCD:

```sh
helm upgrade --install auth-service platform/helm/auth-service --namespace app --create-namespace
```

В основном сценарии деплой выполняет ArgoCD, поэтому вручную ставить Helm chart обычно не нужно.
