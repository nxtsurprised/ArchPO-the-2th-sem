# Возможные Ошибки И Исправления

Этот файл фиксирует практические проблемы, которые могут возникнуть при локальном развертывании k3d/k3s + Cilium.

## Оба curl В NetworkPolicy Demo Завершаются Timeout

Симптом:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -s --max-time 3 http://backend
kubectl -n netpol-demo exec blocked-client -- curl -s --max-time 3 http://backend
```

Обе команды возвращают:

```text
command terminated with exit code 28
```

Это означает, что проблема, скорее всего, не в NetworkPolicy. Если `allowed-client` тоже не проходит, нужно проверить DNS и ClusterIP-сервисы.

Проверка:

```sh
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n netpol-demo exec allowed-client -- cat /etc/resolv.conf
kubectl -n netpol-demo get svc,endpoints,networkpolicy -o wide
```

Если CoreDNS показывает `0/1 Running`, а в логах есть:

```text
plugin/ready: Plugins not ready: "kubernetes"
plugin/kubernetes: Failed to watch
```

значит CoreDNS не может нормально работать с Kubernetes API через Service/ClusterIP.

Дополнительная проверка:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -k -v --connect-timeout 3 --max-time 5 https://10.43.0.1/version
```

Если запрос к `10.43.0.1:443` уходит в timeout, pod не может ходить на Kubernetes Service. В нашем локальном k3d/k3s это произошло при отключенном kube-proxy и включенном Cilium kube-proxy replacement.

Исправление в репозитории уже применено:

- в `platform/cluster/k3d/cluster.yaml` kube-proxy не отключается;
- в `platform/cluster/cilium/cilium-values.yaml` задано `kubeProxyReplacement: false`.

Если кластер был создан старой конфигурацией, его нужно пересоздать:

```sh
./platform/cluster/k3d/delete-cluster.sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
```

После этого проверьте:

```sh
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl get nodes -o wide
```

CoreDNS должен быть `1/1 Running`, а ноды должны быть `Ready`.

## Ноды Долго Остаются NotReady

Симптом:

```sh
kubectl get nodes
```

Ноды остаются `NotReady`.

Возможные причины:

- Cilium еще не установлен.
- Cilium pods не запустились.
- Образ Cilium долго скачивается.

Проверка:

```sh
kubectl get pods -n kube-system
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
```

Если Cilium еще не установлен, выполните:

```sh
./platform/cluster/cilium/install-cilium.sh
```

Если Cilium pods есть, но не готовы, посмотрите события:

```sh
kubectl -n kube-system describe pod -l k8s-app=cilium
```

## Команда cilium status Не Работает

Симптом:

```sh
cilium status
```

Команда не найдена или не может подключиться к кластеру.

Проверьте, установлен ли Cilium CLI:

```sh
cilium version --client
```

Проверьте kubectl context:

```sh
kubectl config current-context
kubectl cluster-info
```

Ожидаемый context:

```text
k3d-archpo-local
```

Если context другой:

```sh
kubectl config use-context k3d-archpo-local
```

## Helm Install Cilium Долго Ждет

Симптом: `install-cilium.sh` долго висит на Helm install или Helm upgrade.

Обычно Helm ждет готовности Cilium, Cilium operator или Hubble components.

В другом терминале проверьте:

```sh
kubectl get pods -n kube-system
kubectl -n kube-system get events --sort-by=.lastTimestamp
```

Если образы скачиваются долго, подождите. Если pod находится в `ImagePullBackOff`, проверьте доступ Docker к registry.

## Metrics Server Не Показывает Метрики

Симптом:

```sh
kubectl top nodes
```

возвращает ошибку или сообщает, что metrics API недоступен.

Проверка:

```sh
kubectl -n kube-system get deployment metrics-server
kubectl -n kube-system logs deployment/metrics-server --tail=100
```

Для локального k3d/k3s нужен аргумент `--kubelet-insecure-tls`:

```sh
kubectl -n kube-system patch deployment metrics-server --type=json -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=120s
```

После rollout подождите 30-60 секунд и повторите:

```sh
kubectl top nodes
```

## HPA Не Масштабирует Deployment

Симптом:

```sh
kubectl get hpa hpa-demo
```

показывает `unknown` metrics или replica count не меняется.

Проверьте metrics-server:

```sh
kubectl top pods
kubectl top nodes
```

Проверьте, что load generator запущен:

```sh
kubectl get pod hpa-load-generator
kubectl logs hpa-load-generator --tail=20
```

Проверьте HPA:

```sh
kubectl describe hpa hpa-demo
```

HPA принимает решения периодически, поэтому после запуска нагрузки нужно подождать несколько минут.

## Istio CRD Не Найдены При Dry-run

Симптом:

```text
no matches for kind "Gateway" in version "networking.istio.io/v1beta1"
ensure CRDs are installed first
```

Причина: Istio еще не установлен, поэтому Kubernetes не знает CRD `Gateway`, `VirtualService`, `DestinationRule`.

Исправление:

```sh
./platform/mesh/install-istio.sh
kubectl get crd gateways.networking.istio.io
kubectl get crd virtualservices.networking.istio.io
kubectl get crd destinationrules.networking.istio.io
```

После этого dry-run для Istio manifest должен пройти.

## Namespace istio-system Застрял В Terminating

Симптом:

```sh
kubectl get namespace istio-system -o yaml
```

В статусе есть:

```text
NamespaceDeletionDiscoveryFailure
metrics.k8s.io/v1beta1: stale GroupVersion discovery
```

Это значит, что namespace уже пустой, но Kubernetes не может завершить удаление из-за сломанного API discovery для metrics-server.

Сначала попробуйте восстановить metrics-server:

```sh
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl rollout restart deployment metrics-server -n kube-system
kubectl rollout status deployment metrics-server -n kube-system --timeout=120s
```

Для локального demo можно удалить stale APIService:

```sh
kubectl delete apiservice v1beta1.metrics.k8s.io
kubectl get namespace istio-system -w
```

После удаления namespace можно повторить:

```sh
./platform/mesh/install-istio.sh
```

## Istio Ingress Gateway Running, Но 0/1 Ready

Симптом:

```sh
kubectl get pods -n istio-system
kubectl logs -n istio-system deployment/istio-ingressgateway -c istio-proxy --tail=120
```

В логах gateway есть:

```text
dial tcp <istiod-service-ip>:15012: i/o timeout
failed to generate workload certificate
```

Это означает, что gateway pod не может дойти до `istiod` через Kubernetes Service. В локальном k3d/k3s это может быть временная проблема Cilium/ClusterIP connectivity после установки.

Проверки:

```sh
kubectl get svc,endpoints -n istio-system
kubectl get pods -n kube-system -o wide
kubectl get networkpolicy -A
```

Исправление, которое помогло в локальной проверке:

```sh
kubectl rollout restart ds/cilium -n kube-system
kubectl rollout status ds/cilium -n kube-system --timeout=180s
kubectl rollout restart deployment/istio-ingressgateway -n istio-system
kubectl rollout status deployment/istio-ingressgateway -n istio-system --timeout=180s
```

После этого ожидаемо:

```text
istio-ingressgateway-...   1/1 Running
istiod-...                 1/1 Running
```

## curl На localhost:8080 Возвращает 000

Симптом:

```sh
./platform/rate-limiting/validation.sh
```

Все ответы выглядят так:

```text
01  000
02  000
```

Причина: на локальном `localhost:8080` нет активного forwarding до Istio Gateway. В k3d/Docker Desktop `istio-ingressgateway` может иметь `EXTERNAL-IP <pending>`, и это нормально.

Проверка:

```sh
kubectl get svc,endpoints -n istio-system -l app=istio-ingressgateway
```

Исправление: запустите port-forward в отдельном терминале и держите его открытым:

```sh
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
```

После этого в другом терминале:

```sh
curl -i http://localhost:8080/api/demo
./platform/rate-limiting/validation.sh
```

## Rate Limit Service ImagePullBackOff

Симптом:

```text
ImagePullBackOff
docker.io/envoyproxy/ratelimit:v1.5.0: not found
```

Причина: Docker Hub для `envoyproxy/ratelimit` публикует rolling/hash tags, а tag `v1.5.0` может отсутствовать.

Исправление уже внесено в `platform/rate-limiting/ratelimit-service.yaml`:

```yaml
image: envoyproxy/ratelimit:master
```

Примените manifest повторно:

```sh
kubectl apply -f platform/rate-limiting/ratelimit-service.yaml
kubectl rollout status deployment/ratelimit -n rate-limiting --timeout=180s
kubectl get pods -n rate-limiting
```

## Gateway HA Снова Становится 1 Pod

Симптом:

```sh
kubectl get pods -n istio-system -l app=istio-ingressgateway
kubectl get hpa -n istio-system
```

Gateway был вручную масштабирован до 2 pod, но позже снова стал 1 pod.

Причина: Istio HPA может иметь `MINPODS=1` и при низкой CPU-нагрузке возвращать deployment к одному pod.

Для стабильной локальной демонстрации установите minimum replicas:

```sh
kubectl patch hpa istio-ingressgateway -n istio-system --type merge -p '{"spec":{"minReplicas":2}}'
kubectl get hpa -n istio-system
kubectl get pods -n istio-system -l app=istio-ingressgateway
```

## Promtail Остается 0/1 Running

Симптом:

```sh
kubectl get pods -n observability -l app.kubernetes.io/name=promtail
```

Promtail pods долго остаются в состоянии:

```text
READY   STATUS
0/1     Running
```

При этом остальные observability components могут быть готовы:

```sh
kubectl get pods -n observability
```

Проверка:

```sh
kubectl describe pod -n observability -l app.kubernetes.io/name=promtail
kubectl logs -n observability -l app.kubernetes.io/name=promtail --tail=100
```

Типичная ошибка в логах:

```text
Not ready: Unable to find any logs to tail. Please verify permissions, volumes, scrape_config, etc.
```

Причина: Promtail запущен, но не нашел файлов логов, которые должен читать. В локальном k3d/k3s это может произойти, если:

- `__path__` в Promtail config не совпадает с реальными путями `/var/log/containers/*.log`;
- Promtail фильтрует targets по node name, но переменная `HOSTNAME` внутри Pod не равна `spec.nodeName`.

Проверить реальные пути логов можно так:

```sh
kubectl exec -n observability ds/promtail -- sh -c 'find /var/log/containers -maxdepth 1 -type l -o -type f | head -20'
kubectl exec -n observability ds/promtail -- sh -c 'find /var/log/pods -maxdepth 4 -type f | head -20'
```

Исправление уже внесено в manifests:

- `platform/observability/manifests/promtail/promtail-config.yaml` читает стандартные container log symlinks из `/var/log/containers`;
- `platform/observability/manifests/promtail/promtail-daemonset.yaml` задает `HOSTNAME` из `spec.nodeName`.

Примените обновленные manifests и перезапустите DaemonSet:

```sh
kubectl apply -k platform/observability/
kubectl rollout restart daemonset/promtail -n observability
kubectl rollout status daemonset/promtail -n observability --timeout=180s
kubectl get pods -n observability -l app.kubernetes.io/name=promtail
```

Ожидаемый результат:

```text
READY   STATUS
1/1     Running
```

После этого можно проверить поток logs через тестовый Job:

```sh
kubectl apply -f platform/observability/validation/generate-test-logs.yaml
kubectl -n observability logs job/observability-test-logs
```

В Grafana Explore для Loki:

```logql
{namespace="observability", app="observability-test-logs"}
```

## Нужно Начать С Чистого Состояния

Если локальное состояние непонятно или кластер был создан старой конфигурацией, проще пересоздать его:

```sh
./platform/cluster/k3d/delete-cluster.sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
```

Затем снова выполните проверки из `docs/deployment.md`.
