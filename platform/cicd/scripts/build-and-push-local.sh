#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <service> <tag> [branch]" >&2
  exit 1
fi

SERVICE="$1"
TAG="$2"
BRANCH="${3:-part-3}"
NAMESPACE="${NAMESPACE:-infra}"
REPO_URL="${REPO_URL:-https://github.com/nxtsurprised/ArchPO-the-2th-sem.git}"
REGISTRY="${REGISTRY:-local-registry.infra.svc.cluster.local:5000}"
JOB_NAME="kaniko-build-${SERVICE}-${TAG//[^a-zA-Z0-9-]/-}"
KANIKO_CPU_REQUEST="${KANIKO_CPU_REQUEST:-250m}"
KANIKO_MEMORY_REQUEST="${KANIKO_MEMORY_REQUEST:-512Mi}"
KANIKO_CPU_LIMIT="${KANIKO_CPU_LIMIT:-1}"
KANIKO_MEMORY_LIMIT="${KANIKO_MEMORY_LIMIT:-1Gi}"

case "${SERVICE}" in
  auth-service|catalog-service|generation-service|workflow-service)
    CONTEXT_SUB_PATH="part1"
    DOCKERFILE="${SERVICE}/Dockerfile"
    ;;
  pmi-agent)
    CONTEXT_SUB_PATH="part1/pmi-agent"
    DOCKERFILE="Dockerfile"
    ;;
  *)
    echo "Unsupported service: ${SERVICE}" >&2
    exit 1
    ;;
esac

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required" >&2
  exit 1
fi

cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: kaniko
    app.kubernetes.io/part-of: archpo-cicd
    archpo.local/service: ${SERVICE}
spec:
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: kaniko
          image: gcr.io/kaniko-project/executor:v1.23.2
          args:
            - --context=git://${REPO_URL#https://}#refs/heads/${BRANCH}
            - --context-sub-path=${CONTEXT_SUB_PATH}
            - --dockerfile=${DOCKERFILE}
            - --destination=${REGISTRY}/${SERVICE}:${TAG}
            - --destination=${REGISTRY}/${SERVICE}:latest
            - --insecure
            - --skip-tls-verify
          resources:
            requests:
              cpu: ${KANIKO_CPU_REQUEST}
              memory: ${KANIKO_MEMORY_REQUEST}
            limits:
              cpu: "${KANIKO_CPU_LIMIT}"
              memory: ${KANIKO_MEMORY_LIMIT}
EOF

kubectl -n "${NAMESPACE}" wait --for=condition=complete "job/${JOB_NAME}" --timeout=20m
kubectl -n "${NAMESPACE}" logs "job/${JOB_NAME}"

echo "Built and pushed:"
echo "  ${REGISTRY}/${SERVICE}:${TAG}"
echo "  ${REGISTRY}/${SERVICE}:latest"
