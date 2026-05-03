# Terraform: базовая инфраструктура Kubernetes

Этот каталог описывает базовые Kubernetes-ресурсы для локального k3d/k3s-кластера.

Terraform управляет только базовой инфраструктурой:

- namespace: `app`, `infra`, `argocd`, `kafka`, `databases`, `observability`;
- ServiceAccount в namespace `app` для сервисов приложения;
- демо Secret для локального запуска;
- ConfigMap `app-config`;
- минимальный RBAC для чтения `app-config`.

Terraform не разворачивает ArgoCD, Kafka, базы данных, observability stack и микросервисы. Эти части относятся к другим инструментам и следующим блокам.

## Предварительные требования

Должны быть установлены:

- Terraform 1.5 или новее;
- kubectl;
- локальный k3d/k3s-кластер из Block 1.

Проверьте context:

```sh
kubectl config current-context
kubectl get nodes
```

По умолчанию используется context `k3d-archpo-local`.

## Переменные

Для учебного локального запуска в `variables.tf` уже заданы demo-значения, поэтому `terraform plan` не должен спрашивать ввод руками.

Если нужно переопределить значения, создайте локальный файл переменных из примера:

```sh
cd platform/terraform
cp terraform.tfvars.example terraform.tfvars
```

Файл `terraform.tfvars` не должен попадать в Git. Значения по умолчанию и значения в примере являются демонстрационными и не подходят для production.

## Запуск

```sh
cd platform/terraform
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
```

Если context называется иначе:

```sh
terraform plan -var='kube_context=your-context-name'
```

## Проверка

Namespace:

```sh
kubectl get ns app infra argocd kafka databases observability
```

ServiceAccount:

```sh
kubectl get serviceaccount -n app
```

Secret:

```sh
kubectl get secret -n app
kubectl get secret -n databases
```

ConfigMap:

```sh
kubectl get configmap app-config -n app
kubectl describe configmap app-config -n app
```

Outputs Terraform:

```sh
terraform output
```

## Что специально не управляется Terraform

- ArgoCD installation и ArgoCD Application ресурсы.
- Strimzi operator, Kafka cluster и KafkaTopic.
- Deployment/Service/Ingress микросервисов.
- Реальные секреты, kubeconfig, Terraform state в Git.
- Docker Compose из `part1/`.

Так разделяется ответственность: Terraform создает базовые объекты кластера, ArgoCD отвечает за GitOps-синхронизацию, Ansible показывает автоматизированный деплой Kafka через Strimzi.
