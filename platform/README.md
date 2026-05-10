# Platform

Этот каталог содержит локальную Kubernetes-инфраструктуру для первого и второго блоков задания.

В реализации используются:

- k3d/k3s для воспроизводимого локального Kubernetes-кластера.
- Cilium в роли CNI.
- Hubble relay и Hubble UI для наблюдения за сетевыми потоками Cilium.
- Kubernetes HPA для локальной проверки автомасштабирования подов.
- Документация по Cluster Autoscaler как выбранному подходу к автомасштабированию worker-нод.
- Istio Service Mesh, Istio Ingress Gateway и gateway-level rate limiting для Block 3.
- Kubernetes observability: Prometheus, Alertmanager, Loki, Promtail, Grafana, OpenTelemetry Collector и Tempo для Block 4.
- Локальный CI/CD-контур для Block 5: GitHub Actions Self-Hosted Runner, Kaniko, local registry, Helm charts и ArgoCD GitOps sync.
- Локальные dev-зависимости для E2E-проверки Helm-deployed сервисов: PostgreSQL, MongoDB, Valkey, MinIO и ChromaDB.

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

Block 2.3 использует Strimzi Operator и создает легкий локальный Kafka cluster в namespace `kafka`. Namespace `kafka` принадлежит Terraform, а Ansible управляет только Kafka-ресурсами внутри него: Strimzi Operator, `KafkaNodePool`, `Kafka` и `KafkaTopic`.

При необходимости Kafka custom resources можно удалить без удаления namespace:

```sh
cd platform/ansible
ansible-playbook -i inventory/local.yml playbooks/delete-kafka.yml
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
kubectl get kafkanodepool -n kafka
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

Подробный troubleshooting для Ansible/Strimzi находится в `platform/ansible/README.md`.

## Block 3: Ядро системы и трафик

Block 3 добавляет локальный traffic layer без переноса реальных микросервисов из `part1/` в Kubernetes:

- `mesh/` устанавливает Istio и содержит demo workload для retry и outlier detection.
- `ingress/` использует Istio Ingress Gateway напрямую как API Gateway / ingress entrypoint.
- `rate-limiting/` добавляет Envoy global rate limiting через `envoyproxy/ratelimit` и Valkey.

В локальном Docker Desktop + k3d окружении не реализуется настоящий Keepalived VIP. Keepalived требует надежного L2/VRRP-поведения, которое не является переносимым в Docker Desktop. Production-вариант описан в `platform/ingress/README.md`.

### Последовательность запуска Block 3

1. Убедитесь, что кластер и Cilium здоровы:

```sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
kubectl get nodes
kubectl get pods -n kube-system
```

2. Установите Istio:

```sh
./platform/mesh/install-istio.sh
kubectl get pods -n istio-system
istioctl proxy-status
```

3. Deploy traffic demo:

```sh
kubectl apply -f platform/mesh/traffic-demo/namespace.yaml
kubectl apply -f platform/mesh/traffic-demo/services.yaml
kubectl rollout status deployment/traffic-backend-v1 -n traffic-demo --timeout=180s
kubectl rollout status deployment/traffic-backend-v2 -n traffic-demo --timeout=180s
kubectl rollout status deployment/traffic-client -n traffic-demo --timeout=180s
kubectl apply -f platform/mesh/traffic-demo/gateway.yaml
kubectl apply -f platform/mesh/traffic-demo/destinationrule.yaml
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

4. Validate retries and outlier detection objects:

```sh
kubectl get pods -n traffic-demo
kubectl get destinationrule,virtualservice,gateway -n traffic-demo
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
./platform/mesh/traffic-demo/load-test.sh
kubectl apply -f platform/mesh/traffic-demo/fault-injection.yaml
./platform/mesh/traffic-demo/load-test.sh
kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
```

5. Apply ingress gateway HA/PDB:

```sh
kubectl patch deployment istio-ingressgateway -n istio-system --patch-file platform/ingress/gateway-ha.yaml
kubectl patch hpa istio-ingressgateway -n istio-system --type merge -p '{"spec":{"minReplicas":2}}'
kubectl apply -f platform/ingress/pdb.yaml
kubectl rollout status deployment/istio-ingressgateway -n istio-system --timeout=180s
kubectl get pods -n istio-system -l app=istio-ingressgateway
kubectl get hpa -n istio-system
kubectl get pdb -n istio-system
```

6. Deploy Valkey and Envoy Rate Limit Service:

```sh
kubectl apply -f platform/rate-limiting/namespace.yaml
kubectl apply -f platform/rate-limiting/valkey.yaml
kubectl apply -f platform/rate-limiting/ratelimit-configmap.yaml
kubectl apply -f platform/rate-limiting/ratelimit-service.yaml
kubectl rollout status deployment/valkey -n rate-limiting --timeout=180s
kubectl rollout status deployment/ratelimit -n rate-limiting --timeout=180s
```

7. Apply EnvoyFilter:

```sh
kubectl apply -f platform/rate-limiting/envoyfilter-ratelimit.yaml
kubectl get envoyfilter -n istio-system
```

8. Validate HTTP 429:

```sh
kubectl get pods -n rate-limiting
kubectl logs -n rate-limiting deployment/ratelimit
kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
curl -i http://localhost:8080/api/demo
./platform/rate-limiting/validation.sh
```

9. Cleanup commands:

```sh
./platform/rate-limiting/cleanup.sh
./platform/mesh/traffic-demo/cleanup.sh
./platform/mesh/uninstall-istio.sh
```

## Block 4: Observability

Block 4 добавляет Kubernetes observability под `platform/observability`. Это отдельный слой от уже существующего Docker Compose observability в `part1/`: Compose-стек остается для локального запуска приложения, а Kubernetes-стек нужен для проверки платформы в k3d/k3s.

Выбранный стек:

- Metrics: Prometheus.
- Logs: Loki + Promtail.
- Visualization: Grafana.
- Alerts: Alertmanager.
- Traces: OpenTelemetry Collector + Tempo.

Почему выбран этот вариант:

- он продолжает уже реализованное направление из `part1/`;
- Prometheus достаточно для локального и учебного масштаба;
- Loki легче ELK для k3d/k3s;
- Grafana объединяет метрики, логи и traces в одном UI;
- Tempo лучше вписывается в Grafana-экосистему, чем отдельный tracing UI;
- OpenTelemetry Collector оставляет трассировку vendor-neutral.

VictoriaMetrics/VictoriaLogs, ELK, SigNoz и ClickHouse рассмотрены как альтернативы в `platform/observability/stack-comparison.md`, но не разворачиваются в этом блоке.

### Последовательность Запуска Block 4

1. Убедитесь, что k3d cluster запущен:

```sh
./platform/cluster/k3d/create-cluster.sh
kubectl get nodes
```

2. Убедитесь, что Cilium здоров:

```sh
./platform/cluster/cilium/install-cilium.sh
kubectl get pods -n kube-system
```

3. Убедитесь, что Terraform namespace существуют, или создайте namespace вручную:

```sh
cd platform/terraform
terraform init
terraform apply
cd ../..
```

Минимальный ручной вариант без Terraform:

```sh
kubectl apply -f platform/observability/namespace.yaml
```

4. Примените observability manifests вручную:

```sh
kubectl apply -k platform/observability/
```

Или синхронизируйте через ArgoCD child app `observability`, который указывает на `platform/observability`.

5. Проверьте Pods:

```sh
kubectl get pods -n observability
platform/observability/validation/check-observability.sh
```

6. Откройте Grafana:

```sh
kubectl -n observability port-forward svc/grafana 3000:3000
```

Откройте `http://localhost:3000`.

7. Проверьте Grafana datasources:

- `Prometheus`;
- `Loki`;
- `Tempo`.

8. Сгенерируйте тестовые logs:

```sh
kubectl apply -f platform/observability/validation/generate-test-logs.yaml
kubectl -n observability logs job/observability-test-logs
```

9. Проверьте logs в Grafana Explore:

```logql
{namespace="observability", app="observability-test-logs"}
```

### Ограничения Block 4

- Traces могут быть пустыми, пока приложения или Istio/Envoy не настроены отправлять OTLP spans в OpenTelemetry Collector.
- Хранилища Prometheus, Loki, Tempo и Grafana используют `emptyDir`, поэтому данные не переживают пересоздание Pod.
- Реальные email, Telegram или Slack receivers для Alertmanager не настраиваются, чтобы не добавлять secrets.
- Полный AI monitoring не разворачивается: текущий scope документирует PMI Agent metrics, latency/errors/fallback counters и будущие LLM spans/quality dashboards.

## Block 5: CI/CD и окружение разработки

Block 5 добавляет локальный учебный pipeline для сборки и доставки образов в Kubernetes:

- GitHub Actions Self-Hosted Runner выбран потому, что репозиторий находится на GitHub.
- Kaniko используется для сборки images без Docker daemon, как требуется в задании.
- Локальный Docker Registry разворачивается в Kubernetes в namespace `infra`.
- Helm charts для `auth-service`, `catalog-service`, `generation-service` и `workflow-service` лежат в `platform/helm/`.
- `pmi-agent` также остается в Helm/CI контуре как дополнительный сервис для AI-monitoring направления.
- ArgoCD child Applications указывают на реальные Helm chart paths и синхронизируют namespace `app`.

CI/CD поток:

1. Разработчик пушит изменения в код сервиса или запускает workflow вручную.
2. Self-hosted runner стартует GitHub Actions workflow.
3. Workflow запускает Kubernetes Job с Kaniko.
4. Kaniko собирает image и пушит его в local registry.
5. Workflow обновляет `image.repository` и `image.tag` в Helm `values.yaml`.
6. Workflow коммитит изменение обратно в ветку `part-3` с `[skip ci]`.
7. ArgoCD видит новый commit и синхронизирует Helm release.

CI не применяет manifests напрямую через `kubectl apply`; деплой приложений остается GitOps-ответственностью ArgoCD.

### Последовательность запуска Block 5

1. Убедитесь, что k3d cluster запущен:

```sh
./platform/cluster/k3d/create-cluster.sh
kubectl get nodes
```

2. Убедитесь, что Cilium здоров:

```sh
./platform/cluster/cilium/install-cilium.sh
kubectl get pods -n kube-system
```

3. Убедитесь, что Terraform namespaces существуют:

```sh
cd platform/terraform
terraform init
terraform apply
cd ../..
kubectl get ns infra app argocd
```

4. Разверните local registry:

```sh
kubectl apply -f platform/cicd/registry/registry-pvc.yaml
kubectl apply -f platform/cicd/registry/registry-deployment.yaml
kubectl apply -f platform/cicd/registry/registry-service.yaml
kubectl get pods -n infra
```

5. Проверьте registry через port-forward:

```sh
kubectl -n infra port-forward svc/local-registry 5000:5000
curl http://localhost:5000/v2/_catalog
```

6. Зарегистрируйте self-hosted runner вручную по инструкции:

```sh
open platform/cicd/runner/setup-self-hosted-runner.md
```

Runner labels:

```text
self-hosted, local, k3d
```

7. Проверьте Helm charts:

```sh
platform/cicd/scripts/validate-helm-charts.sh
```

8. Убедитесь, что ArgoCD видит child Applications:

```sh
kubectl apply -f platform/argocd/root-app.yaml
kubectl get applications -n argocd
```

9. Запустите workflow вручную в GitHub Actions:

```text
Actions -> Build images and update Helm values -> Run workflow
```

10. Проверьте результат:

```sh
kubectl get pods -n infra
kubectl get pods -n app
kubectl get applications -n argocd
curl http://localhost:5000/v2/_catalog
```

Подробности находятся в `platform/cicd/README.md` и `platform/helm/README.md`.

### Ограничения Block 5

- Это локальный учебный CI/CD, не production pipeline.
- GitHub runner registration token не хранится в репозитории и вводится вручную.
- Для pull images из k3d nodes может потребоваться k3d registry integration; простой `localhost:5000` с хоста не всегда доступен изнутри node containers.
- Kaniko выбран по требованию задания, но для production стоит отдельно оценить BuildKit, Buildah или Podman.
- ArgoCD синхронизирует только изменения, которые уже запушены в Git.
- Runtime-зависимости приложений, например PostgreSQL для `auth-service` и `workflow-service`, должны быть развернуты отдельно; Block 5 описывает CI/CD и Helm deployment, а не production databases.

## Dev Dependencies для E2E

`platform/dev-dependencies` добавляет легкие локальные зависимости в namespace `databases`, чтобы Helm-deployed сервисы могли проходить runtime health/readiness checks:

- PostgreSQL для `auth-service` и `workflow-service`;
- MongoDB для `catalog-service`;
- Valkey/Redis-compatible cache для сервисов, которые используют Redis URL;
- MinIO для `generation-service`;
- ChromaDB для `pmi-agent`.

Ollama не разворачивается по умолчанию, потому что он тяжелый для локального k3d/k3s. Его можно подключить отдельно как внешний локальный endpoint.

Развернуть вручную:

```sh
kubectl apply -k platform/dev-dependencies
platform/dev-dependencies/validation/check-dev-dependencies.sh
```

Или через ArgoCD child app `databases`, который указывает на `platform/dev-dependencies`.

Этот слой готовит платформу к будущему Block 6, но не добавляет Locust, k6 или нагрузочные сценарии.

## Как Читать

Этот README используется как пошаговая инструкция с командами.

Дополнительные пояснения:

- `docs/architecture.md` объясняет локальную архитектуру платформы и выбор k3d/k3s.
- `docs/networking.md` объясняет настройку Cilium, Istio traffic layer и демо для сетевых политик.
- `docs/autoscaling.md` объясняет HPA, metrics-server и почему масштабирование нод описано как дизайн, а не запускается локально.
- `docs/validation.md` объясняет, что проверяет каждый шаг валидации.
- `docs/block3-report.md` содержит отчет по Block 3 с командами и фактическими результатами локальной проверки.
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
