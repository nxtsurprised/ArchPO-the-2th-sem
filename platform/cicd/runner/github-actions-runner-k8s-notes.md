# Runner В Kubernetes: Заметки

Для учебного локального стенда проще запускать self-hosted runner на host-машине. Тогда runner использует локальные `git`, `kubectl`, `helm` и текущий kubeconfig.

Runner внутри Kubernetes тоже возможен, но потребует:

- отдельного runner image;
- безопасной передачи registration token;
- ServiceAccount/RBAC для создания Kaniko Jobs;
- доступа к GitHub;
- аккуратной работы с credentials для push commit обратно в Git.

В Block 5 этот вариант описан как future extension, но не автоматизируется, чтобы не коммитить токены и не усложнять локальный demo.
