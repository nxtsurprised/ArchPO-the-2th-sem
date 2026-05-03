# Заметки По Валидации

Этот файл объясняет, что доказывает каждая команда проверки.

## Проверка Кластера

```sh
kubectl get nodes -o wide
```

Команда подтверждает, что Kubernetes видит ожидаемые k3d/k3s-ноды и что они находятся в состоянии `Ready`.

Для этого задания ожидаемая форма кластера:

- 1 server-нода.
- 2 agent/worker-ноды.

## Проверка Cilium

```sh
kubectl get pods -n kube-system
cilium status
```

Эти команды подтверждают, что компоненты Cilium запущены и работают корректно.

Важные компоненты:

- Cilium agents, запущенные как DaemonSet на нодах кластера.
- Cilium operator.
- Hubble relay и Hubble UI, если они успешно включены.

## Проверка Network Policy

Если оба клиента завершаются по timeout, сначала проверьте DNS:

```sh
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n netpol-demo exec allowed-client -- cat /etc/resolv.conf
```

CoreDNS должен быть `1/1 Ready`. Если CoreDNS `0/1 Ready`, проблема не в NetworkPolicy, а в доступе pod к Kubernetes Service/ClusterIP.

Разрешенный запрос:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -sS --max-time 5 http://backend
```

Он доказывает, что backend Service работает и трафик от подов с label `access: allowed` разрешен.

Заблокированный запрос:

```sh
kubectl -n netpol-demo exec blocked-client -- curl -sS --connect-timeout 5 --max-time 5 http://backend
```

Он должен завершиться по timeout. Это доказывает, что NetworkPolicy применяется и трафик от подов с label `access: blocked` запрещен.

## Проверка Metrics Server

```sh
kubectl top nodes
```

Команда доказывает, что metrics-server установлен и Kubernetes может читать ресурсные метрики нод.

Если команда падает сразу после установки, подождите немного и повторите ее. metrics-server может требоваться время, чтобы собрать metrics с kubelet.

## Проверка HPA

```sh
kubectl get hpa hpa-demo -w
kubectl get deployment hpa-demo -w
```

Эти команды доказывают, что:

- HPA может читать CPU metrics.
- HPA может обновлять количество replica у целевого Deployment.
- Kubernetes создает дополнительные поды для Deployment.

Масштабирование не происходит мгновенно. HPA оценивает метрики периодически, поэтому изменение количества replica может занять несколько минут.

## Проверка Очистки

После удаления демо эти команды не должны показывать demo resources:

```sh
kubectl -n netpol-demo get all
kubectl get deployment hpa-demo
kubectl get hpa hpa-demo
```

Если `netpol-demo` был удален через манифест, команда для namespace может вернуть ошибку not found. Это ожидаемо.
