# Доступ К Local Registry

В локальном k3d/k3s окружении registry открывается через port-forward:

```sh
kubectl -n infra port-forward svc/local-registry 5000:5000
```

После этого с host-машины registry доступен как:

```text
localhost:5000
```

Проверка:

```sh
curl http://localhost:5000/v2/_catalog
```

Для Pod внутри Kubernetes registry доступен как:

```text
local-registry.infra.svc.cluster.local:5000
```

## Важное Ограничение k3d

Если image push выполняется на host в `localhost:5000`, Kubernetes nodes не всегда смогут pull-ить этот image как `localhost:5000/...`: внутри node `localhost` указывает на сам node container, а не на host.

Для стабильной локальной схемы лучше создать k3d cluster с registry integration или использовать in-cluster registry address:

```text
local-registry.infra.svc.cluster.local:5000/<service-name>:<tag>
```

Если нужен pull с host registry, используйте k3d registry integration при создании кластера или импортируйте image в k3d вручную.
