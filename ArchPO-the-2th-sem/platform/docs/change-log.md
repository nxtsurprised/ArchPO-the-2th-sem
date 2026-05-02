# Поток Изменений

Этот файл фиксирует, что было сделано в Block 1 и какие решения были изменены после практической проверки.

## Начальная Реализация

Сначала была добавлена структура `platform/`:

- `cluster/k3d/` для локального k3d/k3s-кластера;
- `cluster/cilium/` для установки Cilium и проверки NetworkPolicy;
- `autoscaling/hpa/` для локальной проверки HPA;
- `autoscaling/cluster-autoscaler/` для описания дизайна worker-node autoscaling.

Кластер был описан как `archpo-local`:

- 1 server-нода;
- 2 agent/worker-ноды;
- проброс `8080 -> 80`;
- проброс `8443 -> 443`.

В k3s были отключены:

- Traefik;
- servicelb;
- flannel;
- встроенный k3s network policy controller.

Это нужно, чтобы Cilium был CNI и применял NetworkPolicy.

## Документация

После добавления манифестов была добавлена документация:

- основной runbook в `platform/README.md`;
- архитектурные пояснения;
- описание сети с Cilium;
- описание HPA и Cluster Autoscaler;
- заметки по валидации.

Позже вся документация была переведена на русский язык. Команды, пути, Kubernetes resource names и технические идентификаторы оставлены без перевода.

## Проверка NetworkPolicy И Найденная Ошибка

При проверке demo были выполнены команды:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -s --max-time 3 http://backend
kubectl -n netpol-demo exec blocked-client -- curl -s --max-time 3 http://backend
```

Обе команды завершились timeout:

```text
command terminated with exit code 28
```

Это было подозрительно, потому что `allowed-client` должен проходить, а `blocked-client` должен блокироваться.

Диагностика показала:

- backend pod был `Running`;
- Service `backend` имел endpoint;
- прямой запрос `allowed-client -> backend pod IP` проходил с HTTP 200;
- запрос `allowed-client -> http://backend` зависал на DNS resolution;
- CoreDNS был `0/1 Running`;
- pod не мог подключиться к Kubernetes Service `10.43.0.1:443`.

Вывод: проблема была не в NetworkPolicy, а в ClusterIP/DNS routing.

## Корректировка kube-proxy Replacement

Первоначально kube-proxy был отключен, а Cilium был настроен на kube-proxy replacement.

Для этого локального k3d/k3s окружения такой вариант оказался нестабильным: pod-to-pod по IP работал, но ClusterIP-сервисы и DNS не работали.

Конфигурация была изменена:

- из `platform/cluster/k3d/cluster.yaml` убрано отключение kube-proxy;
- в `platform/cluster/cilium/cilium-values.yaml` задано `kubeProxyReplacement: false`;
- Hubble relay и Hubble UI оставлены включенными;
- документация обновлена, чтобы объяснять это решение.

Итоговый дизайн:

- Cilium остается CNI;
- Cilium применяет NetworkPolicy;
- kube-proxy отвечает за ClusterIP-сервисы;
- CoreDNS работает штатно.

## Повторная Проверка

После изменения конфигурации кластер был пересоздан:

```sh
./platform/cluster/k3d/delete-cluster.sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
```

Проверка показала:

- все ноды `Ready`;
- Cilium pods `1/1 Running`;
- CoreDNS `1/1 Running`;
- Hubble relay и Hubble UI успешно развернуты.

NetworkPolicy demo после этого сработало правильно:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -sS --max-time 5 http://backend
```

вернул HTML nginx.

```sh
kubectl -n netpol-demo exec blocked-client -- curl -sS --connect-timeout 5 --max-time 5 http://backend
```

завершился timeout, что подтверждает применение NetworkPolicy.

## Текущее Состояние Решения

Текущая версия Block 1 делает следующее:

- поднимает локальный k3d/k3s-кластер;
- устанавливает Cilium как CNI;
- оставляет kube-proxy включенным для стабильной работы локальных ClusterIP-сервисов;
- включает Hubble;
- проверяет NetworkPolicy через allowed/blocked clients;
- проверяет HPA через CPU-loadable demo app;
- документирует Cluster Autoscaler как дизайн масштабирования worker-нод без добавления cloud credentials.
