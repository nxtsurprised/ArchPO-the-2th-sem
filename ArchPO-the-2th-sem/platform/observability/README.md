# Block 4: Observability Для Kubernetes

Этот каталог добавляет Kubernetes observability для локального k3d/k3s-кластера.

Важно: в `part1/` уже есть Docker Compose observability: Prometheus, Grafana, Loki, Promtail и Alertmanager. Block 4 не меняет `part1/` и не влияет на Docker Compose. Здесь добавлена отдельная Kubernetes-версия стека для `platform/`.

## Состав

- `Prometheus` собирает метрики Kubernetes, Istio и Pod с annotation `prometheus.io/scrape=true`.
- `Alertmanager` принимает алерты Prometheus и использует локальный receiver без email, Telegram или Slack secrets.
- `Loki` хранит Pod logs.
- `Promtail` собирает logs с Kubernetes nodes через `/var/log/pods`.
- `Tempo` принимает OTLP traces.
- `OpenTelemetry Collector` принимает OTLP gRPC/HTTP и отправляет traces в Tempo.
- `Grafana` содержит provisioned datasources и dashboard `Platform overview`.

## Структура

- `kustomization.yaml` перечисляет только deployable manifests.
- `manifests/` содержит Kubernetes-объекты для ArgoCD и ручного деплоя.
- `validation/` содержит ручные проверки и тестовый Job для логов; эти файлы не синхронизируются ArgoCD.
- `stack-comparison.md` объясняет выбор стека и альтернативы.

## Ручная Установка

Из корня репозитория:

```sh
kubectl apply -f platform/observability/namespace.yaml
kubectl apply -k platform/observability/
kubectl get pods -n observability
```

Запустите проверку:

```sh
platform/observability/validation/check-observability.sh
```

Откройте Grafana:

```sh
kubectl -n observability port-forward svc/grafana 3000:3000
```

Затем откройте `http://localhost:3000`.

## Проверка Логов

```sh
kubectl apply -f platform/observability/validation/generate-test-logs.yaml
kubectl -n observability logs job/observability-test-logs
```

В Grafana Explore выберите Loki и выполните:

```logql
{namespace="observability", app="observability-test-logs"}
```

## Проверка Метрик

Prometheus доступен через port-forward:

```sh
kubectl -n observability port-forward svc/prometheus 9090:9090
```

Откройте `http://localhost:9090/targets`.

Kubernetes-приложения будут автоматически scrape-иться, если у их Pod есть annotations:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8000"
prometheus.io/path: "/metrics"
```

## Traces

OTel Collector принимает spans через:

- gRPC: `otel-collector.observability.svc.cluster.local:4317`;
- HTTP: `http://otel-collector.observability.svc.cluster.local:4318`.

Tempo получает traces от Collector и доступен в Grafana как datasource `Tempo`.

Ограничение: реальные traces будут пустыми, пока приложения или Istio/Envoy не настроены отправлять spans. Этот блок не добавляет instrumentation в код приложений.

## AI Monitoring

Текущий легкий уровень AI monitoring:

- технические метрики PMI Agent через `/metrics`, если сервис развернут в Kubernetes;
- fallback counters;
- pipeline latency;
- ошибки и алерты на основе Prometheus rules.

Не реализовано в этом блоке:

- учет token usage;
- prompt/response tracing;
- LLM quality dashboards;
- отдельный Langfuse/OpenLLMetry-style стек.

Будущее расширение:

- добавить OpenTelemetry spans вокруг LLM calls в PMI Agent;
- передавать model, provider, latency, token usage и fallback reason как span attributes;
- строить quality dashboards на основе eval-suite;
- рассмотреть Langfuse или OpenLLMetry-style подход, если потребуется более глубокая LLM observability.

## Ограничения

- Стек не является production-ready.
- Хранилища используют `emptyDir`; данные удаляются при пересоздании Pod.
- ELK, SigNoz, ClickHouse, VictoriaMetrics Cluster и VictoriaLogs не разворачиваются.
- Alert `PodCrashLooping` требует kube-state-metrics. Без kube-state-metrics правило загружается, но не имеет данных для оценки.
