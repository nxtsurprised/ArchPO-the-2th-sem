# Local Registry

Этот каталог содержит легкий Docker Registry v2 для локального CI/CD demo.

Namespace: `infra`. Он уже создается Terraform в Block 2.

Установка:

```sh
kubectl apply -f platform/cicd/registry/registry-pvc.yaml
kubectl apply -f platform/cicd/registry/registry-deployment.yaml
kubectl apply -f platform/cicd/registry/registry-service.yaml
kubectl get pods -n infra -l app.kubernetes.io/name=local-registry
```

Доступ с host:

```sh
kubectl -n infra port-forward svc/local-registry 5000:5000
curl http://localhost:5000/v2/_catalog
```

Image naming:

```text
localhost:5000/auth-service:<tag>
local-registry.infra.svc.cluster.local:5000/auth-service:<tag>
```

Для учебного локального стенда registry использует PVC на default storage class k3s/k3d. Если local-path storage недоступен, можно заменить PVC на `emptyDir`, но тогда images будут потеряны при пересоздании Pod.
