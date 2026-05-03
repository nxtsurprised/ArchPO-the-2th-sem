# ArgoCD: App of Apps

Этот каталог показывает GitOps-подход через ArgoCD и паттерн App of Apps.

App of Apps означает, что один корневой ArgoCD `Application` указывает на каталог с дочерними `Application`. Корневое приложение синхронизирует список приложений, а дочерние приложения затем синхронизируют свои собственные manifest/Helm/Kustomize пути.

В этом блоке создается структура GitOps. Полные Kubernetes-манифесты микросервисов еще не реализуются.

## Установка ArgoCD

Сначала должен существовать namespace `argocd`. Его создает Terraform, но скрипт также безопасно создаст namespace, если Terraform еще не запускали.

```sh
./platform/argocd/install-argocd.sh
```

Скрипт:

- создает namespace `argocd`, если его нет;
- применяет официальный stable install manifest ArgoCD через server-side apply;
- ждет готовности `argocd-server`, `argocd-repo-server`, `argocd-application-controller`;
- выводит команды для доступа к UI.

Server-side apply используется потому, что некоторые CRD ArgoCD слишком большие для annotation `kubectl.kubernetes.io/last-applied-configuration` при обычном client-side apply.

## Доступ к UI

```sh
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Пароль начального admin:

```sh
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

Откройте:

```text
https://localhost:8080
```

## Применение root app

```sh
kubectl apply -f platform/argocd/root-app.yaml
```

Проверка:

```sh
kubectl get applications -n argocd
kubectl describe application platform-root -n argocd
```

Если первая установка была прервана ошибкой `metadata.annotations: Too long`, просто запустите `./platform/argocd/install-argocd.sh` повторно после обновления скрипта. Уже созданные ресурсы будут обновлены.

## Что синхронизирует root app

`root-app.yaml` указывает на:

- repository: `https://github.com/nxtsurprised/ArchPO-the-2th-sem.git`;
- branch: `part-3`;
- path: `platform/argocd/apps`;
- automated sync с `prune` и `selfHeal`.

## Дочерние приложения

В `platform/argocd/apps/` описаны дочерние ArgoCD `Application`:

- `kafka`;
- `observability`;
- `databases`;
- `auth-service`;
- `catalog-service`;
- `generation-service`;
- `workflow-service`;
- `pmi-agent`;
- `frontend`.

На текущем этапе они являются GitOps-заготовками. Их `path` указывает на планируемые каталоги `platform/gitops/...`, которые будут заполнены в будущих блоках. Kafka в Block 2 демонстрационно разворачивается через Ansible role и Strimzi, а не через ArgoCD, чтобы не смешивать владение одним и тем же ресурсом.
