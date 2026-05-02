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

## Нужно Начать С Чистого Состояния

Если локальное состояние непонятно или кластер был создан старой конфигурацией, проще пересоздать его:

```sh
./platform/cluster/k3d/delete-cluster.sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
```

Затем снова выполните проверки из `docs/deployment.md`.
