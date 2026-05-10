# Block 5: CI/CD и окружение разработки

Этот блок добавляет локальный учебный CI/CD-контур для Kubernetes:

- GitHub Actions Self-Hosted Runner запускает pipeline локально.
- Kaniko собирает Docker images без Docker daemon внутри build job.
- Локальный Docker Registry в Kubernetes хранит образы.
- CI обновляет `image.repository` и `image.tag` в Helm values.
- ArgoCD замечает изменение в Git и синхронизирует Helm charts в namespace `app`.

Docker Compose из `part1/` не изменяется. Этот контур нужен для Kubernetes/GitOps-сценария.

## Выбранный поток

1. Разработчик пушит код сервиса или запускает workflow вручную.
2. GitHub Actions Self-Hosted Runner берет job.
3. Workflow создает Kubernetes Job с Kaniko.
4. Kaniko собирает image из `part1/` и пушит его в локальный registry.
5. Workflow обновляет `platform/helm/<service>/values.yaml`.
6. Workflow коммитит изменение с `[skip ci]`, чтобы не запустить бесконечный цикл.
7. ArgoCD видит новый commit и синхронизирует приложение.

CI не делает `kubectl apply` для микросервисов. Деплой остается за ArgoCD.

## Что реализовано

- `registry/` - manifests для локального registry `registry:2` в namespace `infra`.
- `runner/` - инструкция по ручной регистрации GitHub Actions self-hosted runner.
- `kaniko/` - пример Kaniko Job и пример docker config secret без реальных учетных данных.
- `scripts/update-helm-image.sh` - обновляет image values в Helm chart.
- `scripts/validate-helm-charts.sh` - запускает `helm lint` и `helm template`.
- `scripts/build-and-push-local.sh` - создает Kaniko Job для ручной сборки одного сервиса.
- `.github/workflows/build-and-update-helm.yml` - workflow для build/push/update Helm values.

Основные Helm-deployed микросервисы Block 5:

- `auth-service`
- `catalog-service`
- `generation-service`
- `workflow-service`

`pmi-agent` остается как optional Helm chart, но не входит в обязательную CI matrix локального E2E. Причина: AI/ML-зависимости (`torch`, `sentence-transformers`, `chromadb` и связанные пакеты) делают Kaniko build тяжелым для локального k3d.

## Быстрый запуск с нуля

1. Поднимите локальный кластер и базовую инфраструктуру:

```sh
./platform/cluster/k3d/create-cluster.sh
./platform/cluster/cilium/install-cilium.sh
kubectl get nodes
```

2. Убедитесь, что namespace `infra` существует. Если Terraform еще не запускался, выполните Block 2:

```sh
cd platform/terraform
terraform init
terraform apply
cd ../..
```

3. Разверните локальный registry:

```sh
kubectl apply -f platform/cicd/registry/registry-pvc.yaml
kubectl apply -f platform/cicd/registry/registry-deployment.yaml
kubectl apply -f platform/cicd/registry/registry-service.yaml
kubectl get pods -n infra
```

4. Откройте registry на localhost для проверки:

```sh
kubectl -n infra port-forward svc/local-registry 5000:5000
curl http://localhost:5000/v2/_catalog
```

5. Зарегистрируйте GitHub Actions self-hosted runner по инструкции:

```sh
open platform/cicd/runner/setup-self-hosted-runner.md
```

Runner должен иметь labels:

```text
self-hosted, local, k3d
```

6. Проверьте Helm charts:

```sh
platform/cicd/scripts/validate-helm-charts.sh
```

7. Проверьте ArgoCD Applications:

```sh
kubectl get applications -n argocd
```

8. Запустите workflow вручную в GitHub Actions:

```text
Actions -> Build images and update Helm values -> Run workflow
```

9. Проверьте результат:

```sh
kubectl get pods -n infra
kubectl get pods -n app
kubectl get applications -n argocd
curl http://localhost:5000/v2/_catalog
```

## Ручная сборка одного сервиса

Если нужно проверить Kaniko без GitHub Actions:

```sh
platform/cicd/scripts/build-and-push-local.sh auth-service manual-test part-3
```

Для `workflow-service` используется такой же Kaniko-путь. Его Dockerfile копирует `workflow-service/` и общий `shared/`, поэтому build context берется из `part1`:

```sh
platform/cicd/scripts/build-and-push-local.sh workflow-service manual-test part-3
```

После этого можно обновить Helm values:

```sh
platform/cicd/scripts/update-helm-image.sh \
  auth-service \
  local-registry.infra.svc.cluster.local:5000/auth-service \
  manual-test
```

## Optional PMI Agent

`pmi-agent` не собирается в default workflow и не синхронизируется ArgoCD автоматически. Chart остается в `platform/helm/pmi-agent`, чтобы AI-monitoring направление можно было включить вручную.

Ручная сборка требует больше ресурсов:

```sh
REGISTRY=k3d-archpo-registry:5000 \
KANIKO_CPU_REQUEST=500m \
KANIKO_MEMORY_REQUEST=1Gi \
KANIKO_CPU_LIMIT=2 \
KANIKO_MEMORY_LIMIT=6Gi \
platform/cicd/scripts/build-and-push-local.sh pmi-agent manual-test part-3
```

После успешной сборки:

```sh
platform/cicd/scripts/update-helm-image.sh \
  pmi-agent \
  k3d-archpo-registry:5000/pmi-agent \
  manual-test

git add platform/helm/pmi-agent/values.yaml
git commit -m "ci: update pmi-agent image tag [skip ci]"
git push origin part-3
```

Затем `pmi-agent` можно синхронизировать вручную через ArgoCD UI или CLI. Для обычной проверки Block 5/E2E это не требуется.

## Важные локальные ограничения

- Registry по адресу `localhost:5000` доступен с машины разработчика, но Kubernetes nodes в k3d могут не видеть этот `localhost`.
- Для стабильного pull image из кластера лучше создавать k3d cluster с registry integration или использовать in-cluster адрес `local-registry.infra.svc.cluster.local:5000`.
- Kaniko выбран, потому что это требуется заданием. Для production стоит отдельно рассмотреть BuildKit, Buildah или Podman, потому что статус поддержки Kaniko является риском.
- Self-hosted runner регистрируется вручную. GitHub registration token временный и не должен попадать в Git.
- ArgoCD синхронизирует только то, что уже запушено в Git. Локальные незакоммиченные изменения ArgoCD не увидит.
- Это учебный локальный контур, не production CI/CD.

## Что проверять после E2E deployment

Для core E2E достаточно 4 сервисов:

- `auth-service`;
- `catalog-service`;
- `generation-service`;
- `workflow-service`.

Проверка состояния:

```sh
kubectl get applications -n argocd
kubectl get pods -n app
kubectl get pods -n databases
```

Ожидаемо core apps и `databases` должны быть `Synced / Healthy`, а pod'ы core-сервисов - `1/1 Running`.

Проверка HTTP:

```sh
kubectl -n app port-forward svc/auth-service 8001:8001
curl http://localhost:8001/health
curl http://localhost:8001/metrics
```

Аналогично:

- `catalog-service`: port `8002`;
- `generation-service`: port `8003`;
- `workflow-service`: port `8004`.

`pmi-agent` optional и не должен блокировать эту проверку.

## Связанные файлы

- [registry/README.md](registry/README.md)
- [runner/README.md](runner/README.md)
- [kaniko/README.md](kaniko/README.md)
- [../helm/README.md](../helm/README.md)
