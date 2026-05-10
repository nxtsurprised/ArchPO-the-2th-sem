# Проверка Observability

Эти файлы не входят в ArgoCD sync path. Они нужны для ручной проверки локального k3d/k3s-кластера.

## Команды

Из корня репозитория:

```sh
kubectl apply -f platform/observability/namespace.yaml
kubectl apply -k platform/observability/
platform/observability/validation/check-observability.sh
kubectl apply -f platform/observability/validation/generate-test-logs.yaml
kubectl -n observability port-forward svc/grafana 3000:3000
```

Не запускайте `kubectl apply -R -f platform/observability/` для всего root-каталога. Внутри есть validation Job, который не должен применяться вместе с основным стеком. Root `kustomization.yaml` перечисляет только deployable manifests.

Откройте `http://localhost:3000`. В этой учебной конфигурации включен anonymous Viewer, поэтому отдельный пароль не нужен.

## Что Проверить В Grafana

- Datasource `Prometheus` должен отвечать на `sum(up)`.
- Datasource `Loki` должен отвечать на `{namespace="observability"}`.
- Datasource `Tempo` должен существовать и проходить basic health check.
- В Explore используйте Loki, чтобы найти logs тестового Job:

```logql
{namespace="observability", app="observability-test-logs"}
```

- В Prometheus UI откройте `Status -> Targets` через port-forward:

```sh
kubectl -n observability port-forward svc/prometheus 9090:9090
```

## Ожидаемые Ограничения

- Traces могут быть пустыми, пока приложения или Istio/Envoy не настроены отправлять OTLP spans в `otel-collector.observability.svc.cluster.local:4317` или `:4318`.
- Alert `PodCrashLooping` использует метрику kube-state-metrics. Если kube-state-metrics не установлен, правило загружается, но не срабатывает.
- Prometheus, Loki, Tempo и Grafana используют `emptyDir` storage; данные удаляются вместе с Pod.
