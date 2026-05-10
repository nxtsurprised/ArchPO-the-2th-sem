# Observability

Этот документ описывает Block 4 для Kubernetes-платформы. Подробное сравнение стеков находится в `platform/observability/stack-comparison.md`, а команды проверки - в `platform/observability/validation/README.md`.

## Что Уже Есть В part1

`part1/` содержит Docker Compose observability:

- Prometheus;
- Grafana;
- Loki;
- Promtail;
- Alertmanager.

Этот слой используется для локального запуска приложения через Docker Compose. Block 4 не меняет код сервисов в `part1/`.

## Что Добавлено Для Kubernetes

`platform/observability` добавляет отдельный Kubernetes-стек:

- Prometheus для metrics;
- Loki и Promtail для logs;
- Grafana для dashboards и Explore;
- Alertmanager для alerts;
- OpenTelemetry Collector и Tempo для traces.

Manifests применяются через Kustomize:

```sh
kubectl apply -k platform/observability/
```

ArgoCD child app `observability` также указывает на `platform/observability`.

## AI Monitoring

Текущий уровень:

- PMI Agent может отдавать технические metrics через `/metrics`;
- Prometheus может собирать latency, errors и fallback counters, если Pod размечен scrape annotations;
- Alertmanager может получать базовые alerts по availability, errors и latency.

Не реализовано сейчас:

- учет token usage;
- prompt/response tracing;
- отдельные LLM quality dashboards;
- тяжелый AI observability стек.

План расширения:

- добавить OpenTelemetry spans вокруг LLM calls;
- передавать model/provider/token usage/fallback reason как span attributes;
- строить quality dashboards на основе eval-suite;
- при необходимости рассмотреть Langfuse или OpenLLMetry-style dashboards.

## Ограничения

Block 4 предназначен для локального k3d/k3s и coursework demo. Он не настраивает production retention, внешние Alertmanager receivers и long-term storage.
