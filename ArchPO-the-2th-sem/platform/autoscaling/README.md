# Автомасштабирование

Этот каталог содержит локальную проверку автомасштабирования для задания.

## Локальная Проверка: HPA

Horizontal Pod Autoscaler масштабирует Kubernetes-нагрузки, изменяя количество реплик подов. В локальном k3d/k3s-кластере он работает после установки metrics-server.

Установите metrics-server:

```sh
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=120s
```

Примените демо:

```sh
kubectl apply -f platform/autoscaling/hpa/demo-app.yaml
kubectl apply -f platform/autoscaling/hpa/hpa.yaml
kubectl wait --for=condition=available deployment/hpa-demo --timeout=120s
```

Создайте нагрузку:

```sh
kubectl apply -f platform/autoscaling/hpa/load-generator.yaml
```

Наблюдайте масштабирование:

```sh
kubectl get hpa hpa-demo -w
kubectl get deployment hpa-demo -w
```

Очистите ресурсы:

```sh
kubectl delete -f platform/autoscaling/hpa/load-generator.yaml --ignore-not-found
kubectl delete -f platform/autoscaling/hpa/hpa.yaml --ignore-not-found
kubectl delete -f platform/autoscaling/hpa/demo-app.yaml --ignore-not-found
```

## Дизайн Масштабирования Нод

HPA масштабирует поды. Он не создает и не удаляет worker-ноды.

Cluster Autoscaler и Karpenter масштабируют worker-ноды. Для этого им нужен реальный инфраструктурный backend, который умеет создавать и удалять машины, например:

- интеграция с cloud provider;
- Cluster API с infrastructure provider;
- другой provider-specific backend, предоставляющий операции жизненного цикла node group.

В обычной локальной k3d/k3s-среде worker-ноды являются Docker-контейнерами, созданными k3d. Там нет стандартного cloud backend или Cluster API backend, к которому Cluster Autoscaler или Karpenter могли бы обратиться. Поэтому реальное масштабирование worker-нод описано здесь как архитектурное решение, а HPA используется для воспроизводимой локальной проверки.

Для этого проекта Cluster Autoscaler выбран как дизайн масштабирования worker-нод. Пример Helm values с placeholders находится в `cluster-autoscaler/values.example.yaml`.
