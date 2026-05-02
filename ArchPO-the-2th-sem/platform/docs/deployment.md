# Инструкция По Развертыванию

Этот файл описывает полный порядок развертывания локальной платформы Block 1: k3d/k3s-кластер, Cilium, проверка NetworkPolicy и HPA.

Команды предполагают, что вы находитесь в корне репозитория `ArchPO-the-2th-sem`.

## 1. Проверить Инструменты

Нужны Docker, k3d, kubectl, Helm и Cilium CLI:

```sh
docker version
k3d version
kubectl version --client
helm version
cilium version --client
```

Если какой-то инструмент не найден, установите его и перезапустите терминал.

## 2. Создать Локальный Кластер

```sh
./platform/cluster/k3d/create-cluster.sh
```

Скрипт создает кластер `archpo-local`, если он еще не существует, и переключает kubectl context на `k3d-archpo-local`.

Проверьте ноды:

```sh
kubectl get nodes -o wide
```

До установки Cilium ноды могут быть `NotReady`. Это нормально, потому что flannel отключен, а Cilium еще не установлен.

## 3. Установить Cilium

```sh
./platform/cluster/cilium/install-cilium.sh
```

Скрипт устанавливает или обновляет Helm release `cilium` в namespace `kube-system` и ждет rollout основных компонентов.

Проверьте результат:

```sh
kubectl get nodes -o wide
kubectl get pods -n kube-system
cilium status
```

Ожидаемо:

- все ноды `Ready`;
- Cilium pods `Running`;
- CoreDNS `1/1 Running`;
- `cilium status` не показывает критических ошибок.

Важно: в этой локальной конфигурации `kubeProxyReplacement: false`. Cilium используется как CNI и применяет NetworkPolicy, а kube-proxy отвечает за ClusterIP-сервисы. Это выбранный рабочий вариант для k3d/k3s.

## 4. Проверить NetworkPolicy

Примените demo:

```sh
kubectl apply -f platform/cluster/cilium/network-policy-demo.yaml
kubectl -n netpol-demo wait --for=condition=available deployment/backend --timeout=120s
kubectl -n netpol-demo wait --for=condition=ready pod/allowed-client --timeout=120s
kubectl -n netpol-demo wait --for=condition=ready pod/blocked-client --timeout=120s
```

Проверьте, что разрешенный клиент проходит:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -sS --max-time 5 http://backend
```

Ожидаемый результат: HTML-страница nginx.

Проверьте, что заблокированный клиент не проходит:

```sh
kubectl -n netpol-demo exec blocked-client -- curl -sS --connect-timeout 5 --max-time 5 http://backend
```

Ожидаемый результат: timeout и `command terminated with exit code 28`.

Очистить demo можно так:

```sh
kubectl delete -f platform/cluster/cilium/network-policy-demo.yaml
```

## 5. Установить Metrics Server

HPA требует метрики ресурсов. Установите metrics-server:

```sh
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=120s
```

Проверьте метрики:

```sh
kubectl top nodes
```

Если метрики появились не сразу, подождите 30-60 секунд и повторите команду.

## 6. Проверить HPA

Примените приложение и HPA:

```sh
kubectl apply -f platform/autoscaling/hpa/demo-app.yaml
kubectl apply -f platform/autoscaling/hpa/hpa.yaml
kubectl wait --for=condition=available deployment/hpa-demo --timeout=120s
kubectl get hpa hpa-demo
```

Создайте нагрузку:

```sh
kubectl apply -f platform/autoscaling/hpa/load-generator.yaml
```

Наблюдайте масштабирование:

```sh
kubectl get hpa hpa-demo -w
```

В другом терминале:

```sh
kubectl get deployment hpa-demo -w
```

HPA масштабирует не мгновенно. Обычно нужно подождать несколько минут, пока metrics-server соберет метрики, а HPA примет решение.

Очистите HPA demo:

```sh
kubectl delete -f platform/autoscaling/hpa/load-generator.yaml --ignore-not-found
kubectl delete -f platform/autoscaling/hpa/hpa.yaml --ignore-not-found
kubectl delete -f platform/autoscaling/hpa/demo-app.yaml --ignore-not-found
```

## 7. Удалить Кластер

Когда локальная проверка завершена:

```sh
./platform/cluster/k3d/delete-cluster.sh
```

Это удалит k3d-кластер `archpo-local` и все ресурсы внутри него.

## Короткий Happy Path

Минимальная последовательность команд:

```sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
kubectl get nodes -o wide
kubectl get pods -n kube-system
cilium status
kubectl apply -f platform/cluster/cilium/network-policy-demo.yaml
kubectl -n netpol-demo wait --for=condition=available deployment/backend --timeout=120s
kubectl -n netpol-demo wait --for=condition=ready pod/allowed-client --timeout=120s
kubectl -n netpol-demo wait --for=condition=ready pod/blocked-client --timeout=120s
kubectl -n netpol-demo exec allowed-client -- curl -sS --max-time 5 http://backend
kubectl -n netpol-demo exec blocked-client -- curl -sS --connect-timeout 5 --max-time 5 http://backend
```
