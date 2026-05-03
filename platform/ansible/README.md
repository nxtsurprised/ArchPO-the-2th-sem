# Ansible: Kafka через Strimzi

Этот каталог содержит Ansible role `strimzi_kafka` для автоматизированного деплоя Kafka в Kubernetes через Strimzi operator.

Роль рассчитана на локальный k3d/k3s-кластер и минимальную конфигурацию:

- namespace `kafka`;
- Strimzi Cluster Operator;
- Kafka cluster `archpo-kafka`;
- KafkaTopic `gost34.workflow.events`;
- 1 replica и ephemeral storage для локальной проверки.

Это учебная локальная конфигурация, а не production-настройка Kafka.

## Предварительные требования

Должны быть установлены:

- Ansible;
- Python-библиотека `kubernetes`;
- kubectl с доступом к локальному кластеру.

Пример установки Python-зависимости:

```sh
python3 -m pip install kubernetes
```

## Установка Ansible collection

```sh
cd platform/ansible
ansible-galaxy collection install -r requirements.yml
```

## Запуск playbook

```sh
cd platform/ansible
ansible-playbook -i inventory/local.yml playbooks/deploy-kafka.yml
```

Роль скачивает официальный manifest Strimzi release во временный файл в `/tmp`, меняет namespace на `kafka`, применяет operator и затем применяет Kafka/KafkaTopic custom resources.

## Проверка Strimzi operator

```sh
kubectl get ns
kubectl get pods -n kafka
kubectl -n kafka rollout status deployment/strimzi-cluster-operator --timeout=180s
```

## Проверка Kafka cluster

```sh
kubectl get kafka -n kafka
kubectl describe kafka archpo-kafka -n kafka
kubectl get pods -n kafka
```

Kafka поднимается не мгновенно. Для локального кластера нормально подождать несколько минут.

## Проверка Kafka topic

```sh
kubectl get kafkatopic -n kafka
kubectl describe kafkatopic gost34.workflow.events -n kafka
```

## Переменные роли

Основные значения находятся в `roles/strimzi_kafka/defaults/main.yml`:

- `kafka_namespace: kafka`;
- `kafka_cluster_name: archpo-kafka`;
- `kafka_topic_name: gost34.workflow.events`;
- `kafka_replicas: 1`;
- `kafka_storage_type: ephemeral`;
- `kafka_topic_partitions: 1`;
- `kafka_topic_replicas: 1`.

Terraform тоже создает namespace `kafka` как базовую инфраструктуру. Ansible только гарантирует, что namespace существует, чтобы playbook можно было запустить отдельно в учебном сценарии. Kafka operator, Kafka cluster и KafkaTopic принадлежат Ansible role.
