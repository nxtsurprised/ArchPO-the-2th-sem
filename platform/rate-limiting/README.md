# Gateway Rate Limiting

Block 3 добавляет rate limiting на уровне Istio Ingress Gateway.

Локальная схема:

- `Valkey` хранит counters. Valkey совместим с Redis protocol, поэтому подходит как Redis backend для demo.
- `envoyproxy/ratelimit` принимает gRPC-запросы от Envoy и проверяет лимиты.
- `EnvoyFilter` добавляет HTTP rate limit filter в `istio-ingressgateway`.
- Для `/api/demo` настроен лимит 5 requests per minute.

В demo используется image `envoyproxy/ratelimit:master`, потому что Docker Hub для этого проекта публикует rolling/hash tags, а semver tag вроде `v1.5.0` может отсутствовать.

## Установка

Сначала должны быть установлены Istio и traffic demo:

```sh
./platform/mesh/install-istio.sh
kubectl apply -f platform/mesh/traffic-demo/namespace.yaml
kubectl apply -f platform/mesh/traffic-demo/services.yaml
kubectl apply -f platform/mesh/traffic-demo/gateway.yaml
kubectl apply -f platform/mesh/traffic-demo/destinationrule.yaml
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

Затем примените rate limiting:

```sh
kubectl apply -f platform/rate-limiting/namespace.yaml
kubectl apply -f platform/rate-limiting/valkey.yaml
kubectl apply -f platform/rate-limiting/ratelimit-configmap.yaml
kubectl apply -f platform/rate-limiting/ratelimit-service.yaml
kubectl rollout status deployment/valkey -n rate-limiting --timeout=180s
kubectl rollout status deployment/ratelimit -n rate-limiting --timeout=180s
kubectl apply -f platform/rate-limiting/envoyfilter-ratelimit.yaml
```

Проверка:

```sh
kubectl get pods -n rate-limiting
kubectl logs -n rate-limiting deployment/ratelimit
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
```

## Как Работает Лимит

`ratelimit-configmap.yaml` задает domain `archpo-gateway` и два простых descriptor:

- `PATH=/api/demo`: 5 requests per minute.
- `remote_address`: 20 requests per minute.

`envoyfilter-ratelimit.yaml` делает две вещи:

- вставляет Envoy HTTP rate limit filter перед router filter;
- добавляет rate limit actions на virtual host `*:80`.

Когда запрос приходит на gateway, Envoy отправляет descriptor в `ratelimit.rate-limiting.svc.cluster.local:8081`. Rate Limit Service проверяет counter в Valkey. Если лимит превышен, gateway возвращает HTTP 429.

## Валидация HTTP 429

Запустите:

```sh
./platform/rate-limiting/validation.sh
```

Ожидаемо первые запросы возвращают `200`, а после превышения лимита появляются `429`.

Если `429` не появляется сразу:

```sh
kubectl get pods -n rate-limiting
kubectl logs -n rate-limiting deployment/ratelimit
kubectl get envoyfilter -n istio-system
istioctl proxy-status
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
```

После применения `EnvoyFilter` gateway может несколько секунд получать новую Envoy-конфигурацию.

## Cleanup

Удалить rate limiting resources, не удаляя Istio:

```sh
./platform/rate-limiting/cleanup.sh
```

## Ограничения Demo

- Valkey запущен в одном pod без persistence.
- Лимиты учебные и маленькие, чтобы быстро увидеть HTTP 429.
- В локальном Docker/k3d окружении `remote_address` может быть общим для многих запросов, потому что трафик проходит через Docker networking.
- Это gateway-level rate limiting. Оно не заменяет auth, quotas и business-level limits внутри приложения.
