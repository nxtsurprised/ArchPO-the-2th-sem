# Настройка GitHub Actions Self-Hosted Runner

Репозиторий размещен на GitHub, поэтому для Block 5 выбран GitHub Actions Self-Hosted Runner.

## Где Получить Команду Регистрации

1. Откройте GitHub repository.
2. Перейдите в `Settings -> Actions -> Runners`.
3. Нажмите `New self-hosted runner`.
4. Выберите OS вашей машины.
5. Выполните команды GitHub локально.

GitHub покажет registration token. Он time-limited и не должен попадать в Git.

## Labels

Runner должен иметь labels:

```text
self-hosted
local
k3d
```

Workflow в `.github/workflows/build-and-update-helm.yml` использует:

```yaml
runs-on: [self-hosted, local, k3d]
```

## Требования К Машине Runner

- `git`
- `kubectl`
- `helm`
- доступ к локальному k3d/k3s context
- доступ к GitHub для clone/push
- доступ к local registry через Kubernetes service или port-forward

Runner token и kubeconfig не коммитятся.
