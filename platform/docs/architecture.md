# Архитектура Локальной Платформы

Этот блок платформы готовит локальное Kubernetes-окружение, которое достаточно близко к реальному кластеру для проверки сетевого поведения и автомасштабирования, но остается простым для запуска на машине разработчика.

## Что Мы Собираем

Локальная платформа состоит из нескольких уровней:

- Kubernetes-кластер под управлением k3d.
- Cilium как сетевой плагин кластера.
- Istio как service mesh и ingress/API Gateway слой для Block 3.
- Envoy Rate Limit Service и Valkey для gateway-level rate limiting.
- Kubernetes observability слой для Block 4: Prometheus, Alertmanager, Loki, Promtail, Grafana, OpenTelemetry Collector и Tempo.
- Небольшие validation workloads для проверки сетевых политик и автомасштабирования.

k3d запускает k3s-ноды как Docker-контейнеры. Это дает настоящий Kubernetes API и несколько worker-нод без необходимости поднимать облачную инфраструктуру.

## Форма Кластера

Кластер описан в `platform/cluster/k3d/cluster.yaml`.

Он создает:

- 1 server-ноду, на которой работает Kubernetes control plane.
- 2 agent-ноды, которые выполняют роль worker-нод.
- k3d load balancer container для проброса портов с хоста в кластер.

Открытые порты:

- `localhost:8080` на порт кластера `80`.
- `localhost:8443` на порт кластера `443`.

Эти порты зарезервированы для ingress-проверок. В Block 3 самый переносимый способ открыть Istio Ingress Gateway локально:

```sh
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
```

После этого HTTP gateway requests доступны через `http://localhost:8080`.

Block 3 не переносит существующее приложение из `part1/` в Kubernetes. Для проверки service mesh используется отдельный lightweight demo workload.

## Почему k3d/k3s

k3d/k3s выбран, потому что он:

- достаточно легкий для локальной разработки;
- воспроизводится небольшим YAML-конфигом;
- совместим с локальными Docker-based workflow;
- подходит для проверки CNI-поведения с Cilium.

Это также сохраняет существующий Docker Compose setup в `part1/`. Вся platform-работа изолирована в каталоге `platform/`.

## Отключенные Компоненты k3s

k3s обычно устанавливает несколько стандартных сетевых компонентов. Часть из них пересекается с Cilium, поэтому они отключены:

- Traefik отключен, потому что ingress/API Gateway в Block 3 реализован через Istio Ingress Gateway.
- servicelb отключен, потому что локальным load balancer behavior управляет k3d.
- flannel отключен, потому что Cilium используется как CNI.
- k3s network policy controller отключен, потому что политики применяет Cilium.

kube-proxy оставлен включенным. Это осознанный выбор для локального k3d/k3s: Cilium отвечает за pod networking и применение network policy, а kube-proxy сохраняет стабильную работу ClusterIP-сервисов и DNS.

В локальном окружении можно пытаться включать Cilium kube-proxy replacement, но в этом проекте он отключен, потому что при проверке ломал доступ pod к ClusterIP-сервисам, включая `kubernetes.default` и `kube-dns`.

## Скрипты

`platform/cluster/k3d/create-cluster.sh` создает кластер, если он еще не существует, и переключает `kubectl` на context `k3d-archpo-local`.

`platform/cluster/k3d/delete-cluster.sh` удаляет кластер, если он существует.

Оба скрипта используют `set -euo pipefail` и специально оставлены небольшими, чтобы их было легко читать и повторно запускать.

## Block 3 Traffic Layer

Istio устанавливается отдельно через `platform/mesh/install-istio.sh`. Конфигурация находится в `platform/mesh/istio-values.yaml`.

Локально Istio Ingress Gateway используется напрямую как API Gateway. Для отказоустойчивости в пределах локального кластера задаются две replicas и `PodDisruptionBudget`. Это не является production HA: в Docker Desktop + k3d нет надежного Keepalived VIP/L2 failover. Production-вариант может использовать HAProxy/Keepalived или внешний Load Balancer перед несколькими ingress gateway replicas.

Rate limiting реализован на gateway level: Envoy filter вызывает `envoyproxy/ratelimit`, а counters хранятся в Valkey.

## Block 4 Observability

`platform/observability` добавляет легкий Kubernetes observability стек для локального k3d/k3s. Он не заменяет Docker Compose observability в `part1/`, а переносит то же направление в Kubernetes.

Потоки данных:

- Prometheus scrape-ит Kubernetes API/nodes, annotated Pods, Istio components и PMI Agent candidates.
- Promtail читает Pod logs с node filesystem и отправляет их в Loki.
- Grafana подключается к Prometheus, Loki и Tempo через provisioned datasources.
- Prometheus отправляет alerts в локальный Alertmanager receiver без внешних secrets.
- OpenTelemetry Collector принимает OTLP gRPC/HTTP и экспортирует traces в Tempo.

В этой версии хранилища используют `emptyDir`, потому что цель - воспроизводимая локальная проверка, а не production retention.
