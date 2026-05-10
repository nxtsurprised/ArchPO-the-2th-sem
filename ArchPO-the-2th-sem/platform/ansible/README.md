# Ansible — Kafka через Strimzi

Памятка по деплою Kafka в локальный k3d/k3s-кластер через Ansible и Strimzi Operator.

Реализует задание 2.3: Ansible Role для автоматизированного деплоя Kafka в Kubernetes.

---

## Что создаётся

| Ресурс | Имя | Namespace | Что это |
|--------|-----|-----------|---------|
| Strimzi Cluster Operator | `strimzi-cluster-operator` | `kafka` | Оператор, который управляет Kafka |
| KafkaNodePool | `archpo-kafka-pool` | `kafka` | Один broker/controller node в KRaft mode |
| Kafka | `archpo-kafka` | `kafka` | Kafka cluster |
| KafkaTopic | `gost34-workflow-events` | `kafka` | Topic `gost34.workflow.events` |
| KafkaUser | `archpo-app` | `kafka` | Шаблон есть, по умолчанию не применяется |

Bootstrap address для приложений внутри Kubernetes:

```text
archpo-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092
```

---

## Ответственность

| Инструмент | Что делает |
|------------|------------|
| Terraform | Создаёт namespace `kafka` |
| Ansible | Устанавливает Strimzi и Kafka-ресурсы внутри `kafka` |
| ArgoCD | В этом блоке только показывает GitOps-заготовку для `kafka` |

> Namespace `kafka` не удаляется Ansible, потому что им владеет Terraform.

---

## Предварительные требования

| Компонент | Проверка |
|-----------|----------|
| k3d/k3s cluster | `kubectl get nodes` |
| Cilium | `cilium status` |
| Terraform Block 2.1 | `kubectl get ns kafka` |
| Ansible | `ansible --version` |
| kubernetes.core | `ansible-galaxy collection list kubernetes.core` |
| Python Kubernetes library | см. раздел ниже |

Проверка текущего Kubernetes context:

```bash
kubectl config current-context
```

Ожидаемый context для локального кластера:

```text
k3d-archpo-local
```

---

## Установка зависимостей

Запускать из каталога `platform/ansible`:

```bash
# Перейти в каталог Ansible
cd platform/ansible

# Установить Ansible collection для Kubernetes
ansible-galaxy collection install -r requirements.yml
```

На macOS с Homebrew Ansible использует свой Python. В `inventory/local.yml` зафиксирован interpreter:

```yaml
ansible_python_interpreter: /opt/homebrew/Cellar/ansible/13.6.0/libexec/bin/python
```

Установить Python library нужно именно в этот interpreter:

```bash
/opt/homebrew/Cellar/ansible/13.6.0/libexec/bin/python -m pip install kubernetes
```

Если версия Ansible другая, путь может отличаться. Проверить:

```bash
ansible --version
```

---

## Основные команды

### Деплой Kafka

```bash
# Из каталога platform/ansible
ansible-playbook -i inventory/local.yml playbooks/deploy-kafka.yml
```

Что делает playbook:

1. Проверяет namespace `kafka`.
2. Скачивает official Strimzi manifest версии `0.46.0`.
3. Меняет namespace `myproject` на `kafka`.
4. Применяет Strimzi Operator.
5. Ждёт готовности `strimzi-cluster-operator`.
6. Создаёт `KafkaNodePool` и `Kafka`.
7. Ждёт `Kafka Ready=True`.
8. Создаёт `KafkaTopic`.

### Удаление Kafka-ресурсов

```bash
# Удалить Kafka custom resources, но оставить namespace kafka
ansible-playbook -i inventory/local.yml playbooks/delete-kafka.yml
```

Удаляются:

- `KafkaTopic`
- `Kafka`
- `KafkaNodePool`
- `KafkaUser`, если был включён

---

## Статус

```bash
# Все pod'ы Kafka namespace
kubectl get pods -n kafka

# Strimzi Operator
kubectl get deployment strimzi-cluster-operator -n kafka
kubectl -n kafka rollout status deployment/strimzi-cluster-operator --timeout=180s

# Kafka custom resources
kubectl get kafka -n kafka
kubectl get kafkanodepool -n kafka
kubectl get kafkatopic -n kafka

# Подробный статус Kafka
kubectl describe kafka archpo-kafka -n kafka
```

Ожидаемо после успешного запуска:

```text
kubectl get kafka -n kafka
NAME           DESIRED KAFKA REPLICAS   READY
archpo-kafka   1                        True
```

---

## Логи

```bash
# Логи Strimzi Operator
kubectl logs -n kafka deployment/strimzi-cluster-operator --tail=100

# Следить за логами operator
kubectl logs -n kafka deployment/strimzi-cluster-operator -f

# Найти pod Kafka
kubectl get pods -n kafka

# Логи Kafka pod
kubectl logs -n kafka <kafka-pod-name> --tail=100
```

---

## Отладка

```bash
# События namespace kafka
kubectl get events -n kafka --sort-by=.lastTimestamp

# Подробности по operator
kubectl describe deployment strimzi-cluster-operator -n kafka

# Подробности по Kafka pod
kubectl describe pod -n kafka <pod-name>

# Статус Kafka resource
kubectl get kafka archpo-kafka -n kafka -o yaml

# Проверить, что topic создан
kubectl describe kafkatopic gost34-workflow-events -n kafka
```

---

## Частые ситуации

### `ansible-galaxy: command not found`

Ansible не установлен или не попал в `PATH`.

```bash
brew install ansible
ansible --version
which ansible-playbook
```

### `cd: platform/ansible: No such file or directory`

Вы уже находитесь в `platform/ansible`.

```bash
pwd
```

Если путь заканчивается на `platform/ansible`, повторный `cd platform/ansible` не нужен.

### `the role 'strimzi_kafka' was not found`

Playbook запущен не из `platform/ansible` или Ansible не прочитал `ansible.cfg`.

```bash
cd platform/ansible
ansible-playbook -i inventory/local.yml playbooks/deploy-kafka.yml
```

В `ansible.cfg` задано:

```ini
roles_path = ./roles
```

### `Failed to import the required Python library (kubernetes)`

Пакет `kubernetes` установлен не в тот Python.

```bash
# Посмотреть Python, который использует Ansible
ansible --version

# Установить library в Homebrew Ansible Python
/opt/homebrew/Cellar/ansible/13.6.0/libexec/bin/python -m pip install kubernetes
```

### `Namespace is required for RoleBinding`

Official Strimzi manifest содержит namespaced-ресурсы без явного `metadata.namespace`.

В роли это исправлено через:

```yaml
namespace: "{{ kafka_namespace }}"
```

Если ошибка повторяется, проверьте актуальность task:

```bash
sed -n '20,30p' roles/strimzi_kafka/tasks/main.yml
```

### Playbook долго ждёт Strimzi Operator

На первом запуске Kubernetes скачивает образ operator'а. Это может занять несколько минут.

```bash
kubectl get pods -n kafka -w
kubectl describe deployment strimzi-cluster-operator -n kafka
```

Если pod в `ImagePullBackOff`:

```bash
kubectl describe pod -n kafka -l name=strimzi-cluster-operator
```

Проверьте интернет-доступ Docker/k3d.

### Playbook долго ждёт Kafka

Kafka в Strimzi поднимается не сразу. Для локального кластера 5-10 минут на первом запуске — нормально.

```bash
kubectl get pods -n kafka
kubectl get kafka -n kafka
kubectl describe kafka archpo-kafka -n kafka
kubectl logs -n kafka deployment/strimzi-cluster-operator --tail=100
```

Если Kafka pod в `Pending`, чаще всего не хватает ресурсов Docker Desktop.

### Начать заново

```bash
# Удалить Kafka custom resources
ansible-playbook -i inventory/local.yml playbooks/delete-kafka.yml

# Запустить деплой заново
ansible-playbook -i inventory/local.yml playbooks/deploy-kafka.yml
```

Namespace `kafka` останется на месте.

---

## Ограничения

- Один Kafka broker/controller node.
- KRaft mode, без ZooKeeper.
- Ephemeral storage.
- Replication factor `1`.
- Plain internal listener без TLS/auth.
- Не production-ready.
- Предназначено для локальной проверки платформенного задания.

---

## Связь с заданием

| Пункт | Где реализовано |
|-------|-----------------|
| Ansible Role | `roles/strimzi_kafka` |
| Установка Strimzi | `roles/strimzi_kafka/tasks/main.yml` |
| Kafka cluster | `templates/kafka-cluster.yaml.j2` |
| Kafka topic | `templates/kafka-topic.yaml.j2` |
| Запуск | `playbooks/deploy-kafka.yml` |
| Очистка | `playbooks/delete-kafka.yml` |
