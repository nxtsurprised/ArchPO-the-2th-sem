# Istio Ingress Gateway

В Block 3 Istio Ingress Gateway используется напрямую как Ingress Controller и API Gateway.

Это закрывает требование "Ingress Controller / API Gateway directly": внешний HTTP-трафик входит в кластер через `istio-ingressgateway`, дальше Istio применяет `Gateway`, `VirtualService`, retry policy, outlier detection и rate limiting на уровне Envoy.

## Что Реализовано Локально

- Istio ingress gateway включен в `platform/mesh/istio-values.yaml`.
- Gateway запускается с двумя replicas, если хватает локальных ресурсов.
- `platform/ingress/gateway-ha.yaml` содержит небольшой patch для replicas и anti-affinity.
- `platform/ingress/pdb.yaml` добавляет `PodDisruptionBudget` с `minAvailable: 1`.
- для локальной проверки `localhost:8080` открывается через `kubectl port-forward`.

Применение:

```sh
kubectl patch deployment istio-ingressgateway -n istio-system --patch-file platform/ingress/gateway-ha.yaml
kubectl patch hpa istio-ingressgateway -n istio-system --type merge -p '{"spec":{"minReplicas":2}}'
kubectl apply -f platform/ingress/pdb.yaml
kubectl rollout status deployment/istio-ingressgateway -n istio-system --timeout=180s
```

Проверка:

```sh
kubectl get pods -n istio-system -l app=istio-ingressgateway
kubectl get hpa -n istio-system
kubectl get pdb -n istio-system
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
```

`kubectl port-forward` нужно держать запущенным в отдельном terminal tab на время curl-проверок.

## Почему Нет Keepalived В k3d

Keepalived обычно дает Virtual IP через VRRP/L2-сетевое поведение. В локальном Docker Desktop + k3d окружении такой VIP не является надежной и переносимой проверкой: Docker networking скрывает часть L2-механики, а поведение отличается между macOS, Windows и Linux.

Поэтому в локальном блоке не создается фейковый Keepalived. Вместо этого проверяется то, что воспроизводимо:

- несколько replicas ingress gateway;
- PDB, который не дает добровольно удалить все ingress pod одновременно;
- единая точка входа через Istio Gateway;
- маршрутизация и rate limiting на Envoy gateway.

## Production Вариант

В bare-metal или production-среде перед несколькими `istio-ingressgateway` replicas можно поставить:

- HAProxy + Keepalived с Virtual IP;
- внешний аппаратный или программный Load Balancer;
- cloud LoadBalancer service.

В таком варианте HAProxy или внешний балансировщик держит стабильный entrypoint, а Istio Ingress Gateway остается API Gateway внутри Kubernetes.
