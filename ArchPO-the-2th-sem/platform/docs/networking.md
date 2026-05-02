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
