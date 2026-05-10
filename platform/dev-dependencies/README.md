# Dev dependencies для E2E-проверки

Этот слой добавляет легкие Kubernetes-зависимости для локальной проверки Helm-deployed микросервисов. Он нужен, чтобы сервисы могли стартовать, проходить readiness/health checks и быть готовыми к будущему Block 6 с нагрузочным тестированием.

Это не production database layer и не Block 6.

## Почему зависимости отдельно

Helm charts микросервисов описывают сами приложения: Deployment, Service, probes, image и connection settings. Базы данных, cache и object storage вынесены отдельно, потому что:

- они переиспользуются несколькими сервисами;
- их можно включать только для локальной E2E-проверки;
- ArgoCD может синхронизировать их отдельным child app `databases`;
- Docker Compose из `part1/` остается независимым и не ломается.

## Что разворачивается

Namespace: `databases`.

| Зависимость | Kubernetes Service | Для чего нужна |
| --- | --- | --- |
| PostgreSQL | `postgres:5432` | `auth-service`, `workflow-service` |
| MongoDB | `mongodb:27017` | `catalog-service` |
| MongoDB alias | `mongo:27017` | Совместимость с текущими Helm values |
| Valkey | `valkey:6379` | Redis-compatible cache |
| Redis alias | `redis:6379` | Совместимость с текущими Helm values |
| MinIO | `minio:9000`, console `9001` | `generation-service` |
| ChromaDB | `chromadb:8000` | `pmi-agent` |
| Chroma alias | `chroma:8005` | Совместимость с текущими Helm values |

Ollama не разворачивается по умолчанию: он тяжелый для локального k3d/k3s. Для PMI Agent его можно подключить как внешний локальный endpoint или заменить mock endpoint в отдельной проверке.

## Какие сервисы что используют

- `auth-service` -> PostgreSQL, Redis/Valkey.
- `workflow-service` -> PostgreSQL, Kafka.
- `catalog-service` -> MongoDB, Kafka, Redis/Valkey.
- `generation-service` -> MinIO, Kafka, Redis/Valkey.
- `pmi-agent` -> ChromaDB, Redis/Valkey, optional Ollama.

Kafka разворачивается отдельно через уже существующий Block 2/Ansible/Strimzi путь и не входит в этот каталог.

## Secrets

Manifests используют уже созданные Terraform secrets:

- `postgres-secret` в namespace `databases`;
- `mongo-secret` в namespace `databases`;
- `redis-secret` в namespace `databases`;
- `minio-secret` в namespace `databases`.

Terraform также создает mirror secrets с теми же именами в namespace `app`, потому что Kubernetes `secretKeyRef` не может читать Secret из другого namespace. Это нужно для стабильного запуска Helm-deployed сервисов без ручного копирования secrets.

Ожидаемые ключи:

```text
postgres-secret:
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_DB

mongo-secret:
  MONGO_INITDB_ROOT_USERNAME
  MONGO_INITDB_ROOT_PASSWORD

redis-secret:
  REDIS_PASSWORD

minio-secret:
  MINIO_ROOT_USER
  MINIO_ROOT_PASSWORD
```

Valkey в локальном demo запускается без password, даже если `redis-secret` существует. Это упрощение для локальной проверки.

## Развертывание

Из корня репозитория:

```sh
kubectl apply -k platform/dev-dependencies
```

Если используется ArgoCD App of Apps, child app `databases` указывает на этот каталог:

```sh
kubectl apply -f platform/argocd/root-app.yaml
kubectl get applications -n argocd
```

## Валидация

```sh
platform/dev-dependencies/validation/check-dev-dependencies.sh
```

Проверить вручную:

```sh
kubectl get pods -n databases
kubectl get svc -n databases
kubectl get endpoints -n databases
```

DNS-проверка:

```sh
kubectl apply -f platform/dev-dependencies/validation/dns-check-pod.yaml
kubectl -n databases exec -it dns-check -- nslookup postgres.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup mongodb.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup redis.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup valkey.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup minio.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup chromadb.databases.svc.cluster.local
kubectl delete pod dns-check -n databases
```

## Проверка приложений после запуска зависимостей

```sh
kubectl get pods -n app
kubectl logs -n app deployment/auth-service
kubectl logs -n app deployment/catalog-service
kubectl logs -n app deployment/generation-service
kubectl logs -n app deployment/workflow-service
```

Если сервис все еще падает:

```sh
kubectl describe pod -n app <pod-name>
kubectl logs -n app <pod-name> --previous
```

## Core E2E-проверка

После запуска dev-dependencies и обновления Helm image tags core-система считается готовой к локальной E2E-проверке, если:

```sh
kubectl get pods -n app
kubectl get pods -n databases
kubectl get applications -n argocd
```

Ожидаемое состояние:

- `auth-service`, `catalog-service`, `generation-service`, `workflow-service` - `1/1 Running`;
- dependency pods в `databases` - `Running`;
- MinIO buckets job - `Completed`;
- ArgoCD apps `auth-service`, `catalog-service`, `generation-service`, `workflow-service`, `databases` - `Synced / Healthy`.

`pmi-agent` не входит в обязательный core E2E: он optional из-за тяжелых AI/ML-зависимостей и отсутствия Ollama по умолчанию.

Проверка health/metrics через port-forward:

```sh
kubectl -n app port-forward svc/auth-service 8001:8001
curl http://localhost:8001/health
curl http://localhost:8001/metrics
```

```sh
kubectl -n app port-forward svc/catalog-service 8002:8002
curl http://localhost:8002/health
curl http://localhost:8002/metrics
```

```sh
kubectl -n app port-forward svc/generation-service 8003:8003
curl http://localhost:8003/health
curl http://localhost:8003/metrics
```

```sh
kubectl -n app port-forward svc/workflow-service 8004:8004
curl http://localhost:8004/health
curl http://localhost:8004/metrics
```

Каждый port-forward держит терминал занятым. Для следующего сервиса откройте новый терминал или остановите предыдущий port-forward через `Ctrl+C`.

OpenAPI доступен на `/docs`:

```text
http://localhost:8001/docs
http://localhost:8002/docs
http://localhost:8003/docs
http://localhost:8004/docs
```

Health/metrics проверяют runtime-интеграцию и readiness. Полный пользовательский сценарий с JWT, payloads и gateway-запросами лучше оформить отдельным шагом перед Block 6.

## Подготовка к будущему Block 6

Этот слой нужен, чтобы будущий load-testing блок мог отправлять запросы через Gateway в реальные микросервисы, которые используют Kafka, Redis/Valkey, базы данных, MinIO и ChromaDB.

Нагрузочные тесты, Locust/k6 и сценарии Block 6 здесь не реализуются.

## Ограничения

- Только локальный k3d/k3s demo.
- Single replica для всех зависимостей.
- Нет HA.
- Нет backup/restore.
- Используется `emptyDir`, данные теряются при пересоздании pod.
- Credentials demo-level и приходят из Terraform secrets.
- Valkey запускается без password.
- Ollama не разворачивается по умолчанию.
- Это не production-ready слой.
