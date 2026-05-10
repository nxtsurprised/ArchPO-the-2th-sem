# Kaniko

Kaniko используется потому, что задание требует build образов без Docker daemon. Это удобно для Kubernetes Job: build выполняется внутри Pod, а image отправляется в local registry.

Ограничение: у Kaniko есть риск по maintenance/status проекта. Для production-стека стоит дополнительно рассмотреть BuildKit, Buildah или Podman. В этом блоке Kaniko оставлен как учебное выполнение требования.

## Пример Secret

`docker-config-secret.example.yaml` показывает формат Docker config secret. Реальные credentials не коммитятся.

Для локального registry без auth secret обычно не нужен.

## Пример Job

`kaniko-job.example.yaml` показывает build `auth-service` из Git context:

```sh
kubectl apply -f platform/cicd/kaniko/kaniko-job.example.yaml
kubectl logs -n infra job/kaniko-build-auth-service-example
```

Для реального workflow Job создается скриптом `platform/cicd/scripts/build-and-push-local.sh`.
