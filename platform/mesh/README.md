# Istio Service Mesh

Block 3 добавляет traffic layer поверх локального k3d/k3s-кластера:

- Istio Service Mesh для управления трафиком между сервисами.
- Istio Ingress Gateway как локальный API Gateway.
- retry policy для повторных запросов при сетевых ошибках и HTTP 5xx.
- circuit-breaker-like настройки через connection pool limits и outlier detection.
- отдельный lightweight demo workload, чтобы не переносить реальные микросервисы из `part1/` в Kubernetes в этом блоке.

## Что Такое Service Mesh

Service Mesh добавляет к pod sidecar proxy. В Istio этот proxy основан на Envoy. Приложение продолжает слушать свой обычный порт, но сетевой трафик проходит через proxy, где можно централизованно управлять retry, timeout, маршрутизацией, telemetry и security policy.

В demo namespace `traffic-demo` включен label:

```yaml
istio-injection: enabled
```

Поэтому новые pod в этом namespace получают sidecar `istio-proxy`.

## Установка Istio

Сначала должен быть запущен локальный кластер из Block 1 и установлен Cilium:

```sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
kubectl get nodes
```

Установите Istio CLI, если его еще нет:

```sh
istioctl version
```

Если команда не найдена, на macOS можно установить:

```sh
brew install istioctl
```

После этого запустите установку из корня репозитория:

```sh
./platform/mesh/install-istio.sh
```

Скрипт:

- проверяет доступ к Kubernetes API;
- проверяет наличие `istioctl`;
- создает namespace `istio-system`;
- устанавливает Istio из `platform/mesh/istio-values.yaml`;
- ждет Ready для `istiod` и `istio-ingressgateway`.

Проверка:

```sh
kubectl get pods -n istio-system
istioctl proxy-status
```

## Traffic Demo

Демо создает:

- namespace `traffic-demo` с auto sidecar injection;
- `traffic-client` на базе `curlimages/curl`;
- `traffic-backend-v1` и `traffic-backend-v2` на базе `kennethreitz/httpbin`;
- Service `traffic-backend`;
- Istio `Gateway`, `VirtualService`, `DestinationRule`.

Применение:

```sh
kubectl apply -f platform/mesh/traffic-demo/namespace.yaml
kubectl apply -f platform/mesh/traffic-demo/services.yaml
kubectl rollout status deployment/traffic-backend-v1 -n traffic-demo --timeout=180s
kubectl rollout status deployment/traffic-backend-v2 -n traffic-demo --timeout=180s
kubectl rollout status deployment/traffic-client -n traffic-demo --timeout=180s
kubectl apply -f platform/mesh/traffic-demo/gateway.yaml
kubectl apply -f platform/mesh/traffic-demo/destinationrule.yaml
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

Проверка sidecar:

```sh
kubectl get pods -n traffic-demo
kubectl get pod -n traffic-demo -l app=traffic-backend -o jsonpath='{.items[0].spec.containers[*].name}'
```

В списке containers должен быть `istio-proxy`.

## Retry Policy

Retry policy описана в `virtualservice.yaml`:

```yaml
retries:
  attempts: 3
  perTryTimeout: 1s
  retryOn: 5xx,connect-failure,refused-stream
```

Это означает: если backend возвращает 5xx или соединение временно ломается, Envoy может повторить запрос до трех раз.

Проверка через gateway:

```sh
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
./platform/mesh/traffic-demo/load-test.sh
```

`port-forward` нужно держать запущенным в отдельном terminal tab. Это самый переносимый локальный способ открыть Istio Gateway в Docker Desktop/k3d без Keepalived и без изменения Block 1 cluster config.

## Circuit Breaker И Outlier Detection

В Istio circuit breaker обычно задается через `DestinationRule`.

В demo включены:

- `connectionPool.tcp.maxConnections`;
- `connectionPool.http.http1MaxPendingRequests`;
- `connectionPool.http.maxRequestsPerConnection`;
- `outlierDetection.consecutive5xxErrors`;
- `outlierDetection.baseEjectionTime`.

Outlier detection временно исключает endpoint из load balancing, если он часто отвечает ошибками. Это не "лечит" сервис, но снижает влияние нестабильного pod на клиентов.

Проверка объектов:

```sh
kubectl get destinationrule,virtualservice,gateway -n traffic-demo
kubectl describe destinationrule traffic-backend -n traffic-demo
```

## Fault Injection

`fault-injection.yaml` временно заменяет обычный `VirtualService` и добавляет задержки и HTTP 500 для `/api/demo`.

Включить:

```sh
kubectl apply -f platform/mesh/traffic-demo/fault-injection.yaml
./platform/mesh/traffic-demo/load-test.sh
```

Вернуть обычную маршрутизацию:

```sh
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

## Cleanup

Удалить только traffic demo:

```sh
./platform/mesh/traffic-demo/cleanup.sh
```

Удалить Istio и Block 3 demo resources:

```sh
./platform/mesh/uninstall-istio.sh
```

Скрипт uninstall не удаляет namespaces и ресурсы Block 1/2.
