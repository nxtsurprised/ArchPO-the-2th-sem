# Отчет По Block 3: Service Mesh, Gateway, Rate Limiting

Этот отчет фиксирует, что было сделано в Block 3 и какими командами это проверялось в локальном k3d/k3s-кластере.

## Цель Block 3

В Block 3 реализован traffic layer для локальной платформы:

- Istio используется как Service Mesh.
- Istio Ingress Gateway используется напрямую как Ingress Controller / API Gateway.
- Retry policy и outlier detection настроены на demo-сервисах.
- Локальная отказоустойчивость gateway показана через 2 replicas и `PodDisruptionBudget`.
- Gateway-level rate limiting реализован через Envoy Rate Limit Service и Valkey.

Реальные микросервисы из `part1/` не переносились в Kubernetes. Для проверки используется отдельный lightweight workload `traffic-demo`.

## Установка Istio

Команда:

```sh
./platform/mesh/install-istio.sh
```

После установки были проверены Istio pods:

```sh
kubectl get pods -n istio-system -w
```

Фактический результат:

```text
NAME                                    READY   STATUS    RESTARTS   AGE
istio-ingressgateway-755b6bfb7f-nh88g   1/1     Running   0          82s
istiod-9fb6ccd49-7ts9n                  1/1     Running   0          15m
```

Это показывает, что `istiod` и ingress gateway запущены.

## Traffic Demo

Демо workload развернут командами:

```sh
kubectl apply -f platform/mesh/traffic-demo/namespace.yaml
kubectl apply -f platform/mesh/traffic-demo/services.yaml
kubectl apply -f platform/mesh/traffic-demo/gateway.yaml
kubectl apply -f platform/mesh/traffic-demo/destinationrule.yaml
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

Проверка proxy status:

```sh
istioctl proxy-status
```

Фактический результат:

```text
NAME                                                   CLUSTER        ISTIOD                     VERSION     SUBSCRIBED TYPES
istio-ingressgateway-755b6bfb7f-nh88g.istio-system     Kubernetes     istiod-9fb6ccd49-7ts9n     1.29.2      4 (CDS,LDS,EDS,RDS)
traffic-backend-v1-f5d99ccc-fhcml.traffic-demo         Kubernetes     istiod-9fb6ccd49-7ts9n     1.29.2      4 (CDS,LDS,EDS,RDS)
traffic-backend-v1-f5d99ccc-tqvtm.traffic-demo         Kubernetes     istiod-9fb6ccd49-7ts9n     1.29.2      4 (CDS,LDS,EDS,RDS)
traffic-backend-v2-764dbd6c5b-2cklj.traffic-demo       Kubernetes     istiod-9fb6ccd49-7ts9n     1.29.2      4 (CDS,LDS,EDS,RDS)
traffic-client-6ffff7dfbb-64g2j.traffic-demo           Kubernetes     istiod-9fb6ccd49-7ts9n     1.29.2      4 (CDS,LDS,EDS,RDS)
```

Это подтверждает, что ingress gateway и demo pods подключены к `istiod` и получают Envoy xDS-конфигурацию.

## Проверка Маршрута Через Gateway

Так как локальный k3d/Docker Desktop не выдает внешний LoadBalancer IP, gateway открывался через `port-forward`:

```sh
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
```

В другом терминале:

```sh
curl -i http://localhost:8080/api/demo
```

Фактический результат:

```text
HTTP/1.1 200 OK
server: istio-envoy
date: Tue, 05 May 2026 21:08:04 GMT
content-type: text/html; charset=utf-8
access-control-allow-origin: *
access-control-allow-credentials: true
content-length: 0
x-envoy-upstream-service-time: 23
```

Ключевой признак: `server: istio-envoy`. Это показывает, что запрос прошел через Istio Ingress Gateway.

## Retry И Outlier Detection

Retry policy настроена в `platform/mesh/traffic-demo/virtualservice.yaml`:

```yaml
retries:
  attempts: 3
  perTryTimeout: 1s
  retryOn: 5xx,connect-failure,refused-stream
```

Circuit-breaker-like настройки и outlier detection заданы в `platform/mesh/traffic-demo/destinationrule.yaml`:

```yaml
connectionPool:
  tcp:
    maxConnections: 20
  http:
    http1MaxPendingRequests: 10
    maxRequestsPerConnection: 5
outlierDetection:
  consecutive5xxErrors: 3
  interval: 10s
  baseEjectionTime: 30s
  maxEjectionPercent: 100
```

Проверка обычного маршрута:

```sh
./platform/mesh/traffic-demo/load-test.sh
```

Фактический результат:

```text
Sending 20 requests to http://localhost:8080/api/demo
01  200
02  200
03  200
04  200
05  200
06  200
07  200
08  200
09  200
10  200
11  200
12  200
13  200
14  200
15  200
16  200
17  200
18  200
19  200
20  200
```

Для демонстрации ошибок можно временно применить fault injection:

```sh
kubectl apply -f platform/mesh/traffic-demo/fault-injection.yaml
./platform/mesh/traffic-demo/load-test.sh
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

## Ingress Gateway HA И PDB

Для локальной отказоустойчивости gateway были включены 2 replicas и PDB:

```sh
kubectl scale deployment istio-ingressgateway -n istio-system --replicas=2
kubectl patch hpa istio-ingressgateway -n istio-system --type merge -p '{"spec":{"minReplicas":2}}'
kubectl apply -f platform/ingress/pdb.yaml
```

Проверка HPA:

```sh
kubectl get hpa -n istio-system
```

Фактический результат:

```text
NAME                   REFERENCE                         TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
istio-ingressgateway   Deployment/istio-ingressgateway   cpu: 3%/80%   2         5         2          33m
istiod                 Deployment/istiod                 cpu: 3%/80%   1         5         1          33m
```

Проверка gateway pods:

```sh
kubectl get pods -n istio-system -l app=istio-ingressgateway
```

Фактический результат:

```text
NAME                                    READY   STATUS    RESTARTS   AGE
istio-ingressgateway-7d4f855db9-bt5f7   1/1     Running   0          93s
istio-ingressgateway-7d4f855db9-l6sn4   1/1     Running   0          3m35s
```

Проверка PDB:

```sh
kubectl get pdb -n istio-system
```

Фактический результат:

```text
NAME                   MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
istio-ingressgateway   1               N/A               1                     3m35s
```

Это не production HA, потому что в Docker Desktop/k3d нет реального Keepalived VIP. Но локально показано, что gateway может иметь несколько replicas, а PDB сохраняет минимум один доступный pod при добровольных disruption.

## Rate Limiting

Компоненты rate limiting:

- `Valkey` как Redis-compatible backend.
- `envoyproxy/ratelimit` как global rate limit service.
- `EnvoyFilter` на `istio-ingressgateway`.

Команды:

```sh
kubectl apply -f platform/rate-limiting/namespace.yaml
kubectl apply -f platform/rate-limiting/valkey.yaml
kubectl apply -f platform/rate-limiting/ratelimit-configmap.yaml
kubectl apply -f platform/rate-limiting/ratelimit-service.yaml
kubectl rollout status deployment/valkey -n rate-limiting --timeout=180s
kubectl rollout status deployment/ratelimit -n rate-limiting --timeout=180s
kubectl apply -f platform/rate-limiting/envoyfilter-ratelimit.yaml
```

Проверка pods:

```sh
kubectl get pods -n rate-limiting
```

Фактический результат:

```text
NAME                         READY   STATUS    RESTARTS   AGE
ratelimit-7f4795d4bd-9hdv8   1/1     Running   0          61s
valkey-8574d88bbb-n4cwn      1/1     Running   0          9m31s
```

Проверка Valkey:

```sh
kubectl exec -n rate-limiting deployment/valkey -- valkey-cli ping
```

Фактический результат:

```text
PONG
```

Проверка HTTP 429:

```sh
./platform/rate-limiting/validation.sh
```

Фактический результат:

```text
Sending 12 requests to http://localhost:8080/api/demo
The demo limit for PATH=/api/demo is 5 requests per minute.
01  200
02  200
03  200
04  200
05  200
06  429
07  429
08  429
09  429
10  429
11  429
12  429
```

Это подтверждает, что Envoy Gateway вызывает Rate Limit Service и после превышения лимита возвращает HTTP 429.

## Практические Проблемы И Исправления

Во время локальной проверки были обнаружены и исправлены несколько важных нюансов.

### Istio CRDs До Установки Istio

До установки Istio dry-run для `Gateway`, `VirtualService`, `DestinationRule` завершался ошибкой:

```text
no matches for kind "Gateway" in version "networking.istio.io/v1beta1"
ensure CRDs are installed first
```

Это ожидаемо: Istio CRDs появляются только после установки Istio.

### Namespace istio-system Застрял В Terminating

При повторной установке `istio-system` был в `Terminating`, потому что discovery ломался на `metrics.k8s.io/v1beta1`.

Проверка:

```sh
kubectl get namespace istio-system -o yaml
```

В статусе была ошибка:

```text
NamespaceDeletionDiscoveryFailure
metrics.k8s.io/v1beta1: stale GroupVersion discovery
```

Для локального кластера это решается восстановлением metrics-server или удалением stale APIService.

### Ingress Gateway Не Мог Дойти До istiod

Gateway pod был `Running`, но `0/1 Ready`. В логах:

```text
dial tcp 10.43.248.35:15012: i/o timeout
failed to generate workload certificate
```

Причина: временная проблема pod-to-Service connectivity после установки. Исправление:

```sh
kubectl rollout restart ds/cilium -n kube-system
kubectl rollout status ds/cilium -n kube-system --timeout=180s
kubectl rollout restart deployment/istio-ingressgateway -n istio-system
kubectl rollout status deployment/istio-ingressgateway -n istio-system --timeout=180s
```

После этого gateway стал `1/1 Running`.

### Localhost:8080 Требует Port-forward

Без port-forward:

```text
curl http://localhost:8080/api/demo
000
```

Проверка service показала:

```text
service/istio-ingressgateway   LoadBalancer   ...   EXTERNAL-IP <pending>
```

Для k3d/Docker Desktop это нормально. Локальная проверка выполняется через:

```sh
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
```

### Ratelimit Image Tag

Первоначальный image tag `envoyproxy/ratelimit:v1.5.0` не существовал в Docker Hub:

```text
docker.io/envoyproxy/ratelimit:v1.5.0: not found
ImagePullBackOff
```

Manifest был исправлен на:

```yaml
image: envoyproxy/ratelimit:master
```

После повторного apply pod стал `1/1 Running`.

## Итог

Block 3 успешно демонстрирует локальное ядро traffic layer:

- Service Mesh: Istio sidecars и `istioctl proxy-status`.
- Gateway/API entrypoint: Istio Ingress Gateway.
- Traffic policies: retry и outlier detection.
- Local gateway fault tolerance: 2 gateway replicas, HPA minReplicas 2, PDB minAvailable 1.
- Rate limiting: Envoy Rate Limit Service + Valkey + EnvoyFilter.
- Проверяемый результат: HTTP 429 после 5 requests per minute на `/api/demo`.
