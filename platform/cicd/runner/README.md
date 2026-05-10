# GitHub Actions Self-Hosted Runner

Этот каталог описывает ручную настройку self-hosted runner для локального CI/CD.

Что важно:

- runner registration token нельзя коммитить;
- runner должен запускаться на машине, где есть доступ к k3d/k3s cluster;
- workflow использует labels `self-hosted`, `local`, `k3d`;
- runner выполняет scripts из `platform/cicd/scripts`.

Минимальная проверка после регистрации:

```sh
git --version
kubectl config current-context
helm version
kubectl get nodes
```

Подробные шаги: `setup-self-hosted-runner.md`.
