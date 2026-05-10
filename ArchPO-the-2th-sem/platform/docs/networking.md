# Сеть С Cilium

В этом блоке Cilium используется как Kubernetes CNI. CNI отвечает за сетевую связность подов и применение сетевых политик.

## Почему Cilium

Cilium выбран, потому что он дает:

- pod-to-pod networking;
- обработку Kubernetes Services;
- применение NetworkPolicy;
- Hubble visibility для наблюдения за сетевыми потоками.

В этой локальной конфигурации Cilium устанавливается через Helm с values из `platform/cluster/cilium/cilium-values.yaml`.

## Процесс Установки Cilium

Скрипт установки находится в `platform/cluster/cilium/install-cilium.sh`.

Он делает четыре вещи:

- добавляет Helm-репозиторий Cilium;
- обновляет индекс репозитория;
- устанавливает или обновляет Helm release `cilium` в `kube-system`;
- ждет rollout для Cilium, Cilium operator, Hubble relay и Hubble UI, если соответствующие компоненты присутствуют.

Скрипт можно запускать повторно. Helm обновит существующий release вместо создания дубликата.

## Важные Values

`kubeProxyReplacement: false` оставляет kube-proxy ответственным за ClusterIP-сервисы.

Это сделано для совместимости с локальным k3d/k3s. При отключенном kube-proxy и включенном Cilium kube-proxy replacement в этом окружении pod могли напрямую ходить на pod IP, но не могли ходить на ClusterIP-сервисы. Из-за этого CoreDNS оставался `0/1 Ready`, а короткие имена вроде `backend` не резолвились.

`hubble.enabled`, `hubble.relay.enabled` и `hubble.ui.enabled` включают наблюдение сетевых потоков Cilium для локальной проверки.

## Демо Network Policy

Демо-манифест находится в `platform/cluster/cilium/network-policy-demo.yaml`.

Он создает:

- namespace `netpol-demo`;
- Deployment `backend` с nginx;
- Service `backend`;
- pod `allowed-client`;
- pod `blocked-client`;
- Kubernetes `NetworkPolicy`.

Политика выбирает поды с `app: backend` и разрешает ingress только от подов с `access: allowed`.

Это означает:

- `allowed-client` может обращаться к `http://backend`.
- `blocked-client` не может обращаться к `http://backend`.

## Что Это Доказывает

Демо показывает, что:

- Cilium установлен как активный CNI;
- поды могут резолвить и вызывать Services;
- Cilium применяет Kubernetes NetworkPolicy;
- трафик можно ограничивать по labels подов.

Запрос от заблокированного клиента должен завершиться по timeout, потому что backend pod не принимает ingress от label set `blocked-client`.

## Block 3: Istio Traffic Layer

Начиная с Block 3, поверх Cilium добавляется Istio.

Роли разделены так:

- Cilium остается CNI и применяет Kubernetes NetworkPolicy.
- Istio управляет L7 HTTP-трафиком через Envoy sidecar и ingress gateway.
- Istio `VirtualService` задает route, timeout и retry policy.
- Istio `DestinationRule` задает connection pool limits и outlier detection.
- Istio `EnvoyFilter` подключает global rate limiting на ingress gateway.

Локальное demo находится в `platform/mesh/traffic-demo/`. Оно не зависит от реальных микросервисов и не меняет Docker Compose setup.

Основные проверки:

```sh
kubectl get pods -n istio-system
istioctl proxy-status
kubectl get pods -n traffic-demo
kubectl get destinationrule,virtualservice,gateway -n traffic-demo
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
```

Rate limiting находится в `platform/rate-limiting/`:

```sh
kubectl get pods -n rate-limiting
kubectl logs -n rate-limiting deployment/ratelimit
./platform/rate-limiting/validation.sh
```

После превышения demo-лимита gateway должен вернуть HTTP 429.
