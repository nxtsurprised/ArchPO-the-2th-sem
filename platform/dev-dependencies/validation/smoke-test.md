# Smoke test dev-зависимостей

Этот smoke test проверяет только dependency layer в namespace `databases`. Он не является Block 6 и не запускает нагрузочные тесты.

## 1. Развернуть зависимости

Из корня репозитория:

```sh
kubectl apply -k platform/dev-dependencies
```

Или через ArgoCD child app `databases`, если root app уже синхронизирован.

## 2. Проверить pods/services

```sh
platform/dev-dependencies/validation/check-dev-dependencies.sh
```

Ожидаемо должны появиться:

- `postgres`
- `mongodb`
- `valkey`
- `minio`
- `chromadb`

## 3. Проверить DNS

```sh
kubectl apply -f platform/dev-dependencies/validation/dns-check-pod.yaml
kubectl -n databases exec -it dns-check -- nslookup postgres.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup mongodb.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup redis.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup valkey.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup minio.databases.svc.cluster.local
kubectl -n databases exec -it dns-check -- nslookup chromadb.databases.svc.cluster.local
```

Удалить pod после проверки:

```sh
kubectl delete pod dns-check -n databases
```

## 4. Проверить приложения

```sh
kubectl get pods -n app
kubectl logs -n app deployment/auth-service
kubectl logs -n app deployment/catalog-service
kubectl logs -n app deployment/generation-service
kubectl logs -n app deployment/workflow-service
```

Если pod в `CrashLoopBackOff`, смотрите:

```sh
kubectl describe pod -n app <pod-name>
kubectl logs -n app <pod-name> --previous
```

Типовые причины:

- image еще не собран или не доступен в k3d registry;
- сервис ждет Kafka, а Kafka еще не поднята;
- Secret отсутствует в namespace, где запускается pod;
- init/migration приложения требует пустую или уже подготовленную БД.

## 5. Проверить core E2E health/metrics

Core E2E для текущего этапа включает:

- `auth-service`;
- `catalog-service`;
- `generation-service`;
- `workflow-service`;
- dev-dependencies в namespace `databases`.

`pmi-agent` optional и не блокирует core E2E.

Проверьте сервисы по одному:

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

Для просмотра реальных API endpoints:

```text
http://localhost:8001/docs
http://localhost:8002/docs
http://localhost:8003/docs
http://localhost:8004/docs
```

## 6. Связь с будущим Block 6

После этого слоя микросервисы смогут обращаться к локальным Postgres, MongoDB, Redis/Valkey, MinIO и ChromaDB. В будущем Block 6 нагрузочный инструмент сможет отправлять запросы через Gateway в сервисы, которые используют эти зависимости.

Locust, k6 или другой load-testing инструмент здесь не добавляется.
