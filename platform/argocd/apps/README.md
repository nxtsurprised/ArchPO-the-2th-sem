# ArgoCD child Applications

Этот каталог читается корневым приложением `platform-root`.

Файлы здесь являются дочерними ArgoCD `Application` для App of Apps pattern:

- `kafka.yaml`;
- `observability.yaml`;
- `databases.yaml`;
- `auth-service.yaml`;
- `catalog-service.yaml`;
- `generation-service.yaml`;
- `workflow-service.yaml`;
- `pmi-agent.yaml`;
- `frontend.yaml`.

Важно: сейчас это GitOps-заготовки. Они показывают структуру будущей синхронизации, но не утверждают, что все сервисы уже развернуты в Kubernetes.

Планируемые пути:

- `platform/gitops/kafka`;
- `platform/gitops/observability`;
- `platform/gitops/databases`;
- `platform/gitops/services/auth-service`;
- `platform/gitops/services/catalog-service`;
- `platform/gitops/services/generation-service`;
- `platform/gitops/services/workflow-service`;
- `platform/gitops/services/pmi-agent`;
- `platform/gitops/services/frontend`.

Если применить root app до появления этих каталогов, дочерние приложения могут показывать ошибку синхронизации из-за отсутствующего path. Это ожидаемое состояние для Block 2. В следующих блоках сюда можно добавить реальные Helm charts, Kustomize overlays или обычные manifest.
