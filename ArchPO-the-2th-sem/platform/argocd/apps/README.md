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

Важно: большинство файлов сейчас являются GitOps-заготовками. Они показывают структуру будущей синхронизации, но не утверждают, что все сервисы уже развернуты в Kubernetes. `observability.yaml` уже указывает на реальные manifests Block 4.

Планируемые пути:

- `platform/gitops/kafka`;
- `platform/observability`;
- `platform/gitops/databases`;
- `platform/gitops/services/auth-service`;
- `platform/gitops/services/catalog-service`;
- `platform/gitops/services/generation-service`;
- `platform/gitops/services/workflow-service`;
- `platform/gitops/services/pmi-agent`;
- `platform/gitops/services/frontend`.

Если применить root app до появления этих каталогов, дочерние приложения-заготовки могут показывать sync error из-за отсутствующего path. Это ожидаемо для сервисов, которые еще не перенесены в Kubernetes. `observability` синхронизируется через Kustomize из `platform/observability`.
