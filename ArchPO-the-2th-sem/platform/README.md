# Platform

Этот каталог содержит локальную Kubernetes-инфраструктуру для первого и второго блоков задания.

В реализации используются:

- k3d/k3s для воспроизводимого локального Kubernetes-кластера.
- Cilium в роли CNI.
- Hubble relay и Hubble UI для наблюдения за сетевыми потоками Cilium.
- Kubernetes HPA для локальной проверки автомасштабирования подов.
- Документация по Cluster Autoscaler как выбранному подходу к автомасштабированию worker-нод.

В репозиторий не добавляются облачные учетные данные, kubeconfig-файлы, секреты или сгенерированное состояние кластера.

## Block 2: Управление конфигурацией

Block 2 добавляет IaC и GitOps-слой поверх локального кластера из Block 1:

- `terraform/` описывает базовые Kubernetes-объекты: namespace, ServiceAccount, demo Secret, ConfigMap и минимальный RBAC.
- `argocd/` устанавливает ArgoCD и задает App of Apps pattern через root Application.
- `ansible/` содержит role для деплоя Kafka через Strimzi operator.

### Ответственность инструментов

| Инструмент | За что отвечает | За что не отвечает |
| --- | --- | --- |
| Terraform | Базовые Kubernetes objects: namespace, ServiceAccount, Secret, ConfigMap, RBAC | ArgoCD Applications, Kafka cluster, микросервисы |
| ArgoCD | GitOps-синхронизация приложений из Git-репозитория | Создание базовых Secret и локальный Ansible-деплой Kafka |
| Ansible | Автоматизированный Kafka deployment через Strimzi | Базовые namespace/ServiceAccount приложения и GitOps-синхронизация |

Kafka namespace создается Terraform как базовая инфраструктура. Ansible role также проверяет, что namespace существует, чтобы playbook можно было запускать отдельно в учебном локальном сценарии; labels Terraform при этом не перезаписываются.

### Последовательность запуска Block 2

1. Убедитесь, что кластер из Block 1 запущен:

```sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
kubectl get nodes
```

2. Запустите Terraform:

```sh
cd platform/terraform
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
cd ../..
```

3. Установите ArgoCD:

```sh
./platform/argocd/install-argocd.sh
```

4. Примените root app:

```sh
kubectl apply -f platform/argocd/root-app.yaml
kubectl get applications -n argocd
```

Дочерние ArgoCD Applications сейчас являются заготовками и указывают на будущие пути `platform/gitops/...`. Это ожидаемо для Block 2: реальные Helm charts или manifest микросервисов не создаются в этом блоке.

5. Запустите Ansible playbook для Kafka:

```sh
cd platform/ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory/local.yml playbooks/deploy-kafka.yml
cd ../..
```

6. Проверьте ресурсы:

```sh
kubectl get ns
kubectl get serviceaccount -n app
kubectl get secret -n app
kubectl get secret -n databases
kubectl get configmap app-config -n app
kubectl get applications -n argocd
kubectl get pods -n kafka
kubectl get kafka -n kafka
kubectl get kafkatopic -n kafka
kubectl describe kafka archpo-kafka -n kafka
```

### Troubleshooting Block 2

Если Terraform не видит кластер, проверьте context:

```sh
kubectl config current-context
terraform plan -var='kube_context=k3d-archpo-local'
```

Если хотите заменить demo-секреты, создайте локальный файл `platform/terraform/terraform.tfvars` из `terraform.tfvars.example`. Этот файл игнорируется Git.

Если `terraform init` не может скачать provider, проверьте доступ к registry Terraform и повторите команду.

Если ArgoCD pods долго не становятся ready:

```sh
kubectl get pods -n argocd
kubectl describe pod -n argocd <pod-name>
```

Если child Applications в ArgoCD показывают ошибку missing path, это нормально для текущего блока. Пути `platform/gitops/...` будут заполнены в будущих блоках.

Если Ansible не находит Kubernetes-модули:

```sh
cd platform/ansible
ansible-galaxy collection install -r requirements.yml
python3 -m pip install kubernetes
```

Если Kafka долго поднимается:

```sh
kubectl get pods -n kafka
kubectl describe kafka archpo-kafka -n kafka
kubectl logs -n kafka deployment/strimzi-cluster-operator
```

## Как Читать

Этот README используется как пошаговая инструкция с командами.

Дополнительные пояснения:

- `docs/architecture.md` объясняет локальную архитектуру платформы и выбор k3d/k3s.
- `docs/networking.md` объясняет настройку Cilium и демо для сетевых политик.
- `docs/autoscaling.md` объясняет HPA, metrics-server и почему масштабирование нод описано как дизайн, а не запускается локально.
- `docs/validation.md` объясняет, что проверяет каждый шаг валидации.
- `docs/deployment.md` содержит полную инструкцию по развертыванию с проверками после каждого этапа.
- `docs/troubleshooting.md` описывает типовые ошибки и способы исправления.
- `docs/change-log.md` фиксирует поток изменений и почему конфигурация была скорректирована.

Если нужно просто развернуть платформу с нуля, начните с `docs/deployment.md`.

## Предварительные Требования

Локально должны быть установлены:

- Docker
- k3d
- kubectl
- Helm
- Cilium CLI

Проверьте, что инструменты доступны:

```sh
docker version
k3d version
kubectl version --client
helm version
cilium version --client
```

## Создание Кластера

Создайте локальный кластер:

```sh
./platform/cluster/k3d/create-cluster.sh
```

Кластер называется `archpo-local` и содержит:

- 1 server-ноду k3s.
- 2 agent/worker-ноды k3s.
- Проброс порта хоста `8080` на порт кластера `80`.
- Проброс порта хоста `8443` на порт кластера `443`.

В k3s отключены стандартные компоненты, которые конфликтуют с Cilium:

- Traefik
- servicelb
- flannel через `--flannel-backend=none`
- встроенный k3s network policy controller

kube-proxy оставлен включенным. Для локального k3d/k3s это более надежный вариант: Cilium остается CNI и применяет NetworkPolicy, а kube-proxy отвечает за ClusterIP-сервисы. В этом окружении режим Cilium kube-proxy replacement может ломать доступ pod к ClusterIP и DNS.

## Установка Cilium

Установите или обновите Cilium:

```sh
./platform/cluster/cilium/install-cilium.sh
```

## Проверка Cilium

Выполните:

```sh
kubectl get nodes -o wide
kubectl get pods -n kube-system
cilium status
```

Ожидаемый результат:

- Все ноды находятся в состоянии `Ready`.
- Поды Cilium запущены в namespace `kube-system`.
- `cilium status` показывает, что Cilium работает корректно.

Опциональный доступ к Hubble UI:

```sh
cilium hubble ui
```

## Демо Сетевой Политики

Примените демо:

```sh
kubectl apply -f platform/cluster/cilium/network-policy-demo.yaml
kubectl -n netpol-demo wait --for=condition=available deployment/backend --timeout=120s
kubectl -n netpol-demo wait --for=condition=ready pod/allowed-client --timeout=120s
kubectl -n netpol-demo wait --for=condition=ready pod/blocked-client --timeout=120s
```

Разрешенный клиент должен получить ответ от backend:

```sh
kubectl -n netpol-demo exec allowed-client -- curl -sS --max-time 5 http://backend
```

Заблокированный клиент должен завершиться по timeout:

```sh
kubectl -n netpol-demo exec blocked-client -- curl -sS --connect-timeout 5 --max-time 5 http://backend
```

Очистите демо:

```sh
kubectl delete -f platform/cluster/cilium/network-policy-demo.yaml
```

## Установка Metrics Server

HPA нужны метрики ресурсов. Установите metrics-server:

```sh
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Для локального k3d/k3s-кластера разрешите metrics-server обращаться к kubelet с self-signed сертификатами:

```sh
kubectl -n kube-system patch deployment metrics-server --type=json -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=120s
kubectl top nodes
```

## Демо HPA

Примените демо-приложение и HPA:

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

Наблюдайте, как HPA масштабирует реплики:

```sh
kubectl get hpa hpa-demo -w
```

В другом терминале можно наблюдать Deployment:

```sh
kubectl get deployment hpa-demo -w
```

Масштабирование может занять несколько минут, потому что metrics-server и HPA собирают и оценивают метрики периодически.

Очистите HPA-демо:

```sh
kubectl delete -f platform/autoscaling/hpa/load-generator.yaml --ignore-not-found
kubectl delete -f platform/autoscaling/hpa/hpa.yaml --ignore-not-found
kubectl delete -f platform/autoscaling/hpa/demo-app.yaml --ignore-not-found
```

## Удаление Кластера

Удалите локальный кластер:

```sh
./platform/cluster/k3d/delete-cluster.sh
```

## Связь С Заданием

Task 1.1: локальный Kubernetes-кластер с Cilium CNI

- `platform/cluster/k3d/cluster.yaml` описывает локальный k3d/k3s-кластер с 1 server-нодой и 2 worker-нодами.
- `platform/cluster/k3d/create-cluster.sh` и `delete-cluster.sh` создают и удаляют кластер.
- Сетевые компоненты k3s, конфликтующие с Cilium, отключены.
- `platform/cluster/cilium/cilium-values.yaml` настраивает Cilium как CNI с включенным Hubble. `kubeProxyReplacement` отключен для совместимости с локальным k3d/k3s.
- `platform/cluster/cilium/install-cilium.sh` устанавливает или обновляет Cilium через Helm.
- `platform/cluster/cilium/network-policy-demo.yaml` проверяет работу сетевых политик через Cilium.

Task 1.2: проверка автомасштабирования и дизайн масштабирования нод

- `platform/autoscaling/hpa/demo-app.yaml`, `hpa.yaml` и `load-generator.yaml` дают локальный сценарий проверки HPA.
- `platform/autoscaling/README.md` описывает HPA и различие между масштабированием подов и worker-нод.
- `platform/autoscaling/cluster-autoscaler/README.md` описывает Cluster Autoscaler как выбранный дизайн масштабирования нод.
- `platform/autoscaling/cluster-autoscaler/values.example.yaml` содержит только placeholders и не содержит учетных данных.
