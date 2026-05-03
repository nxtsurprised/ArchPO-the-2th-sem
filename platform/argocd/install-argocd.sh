#!/usr/bin/env bash
set -euo pipefail

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
ARGOCD_MANIFEST_URL="${ARGOCD_MANIFEST_URL:-https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml}"

kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Server-side apply avoids the large last-applied annotation on ArgoCD CRDs.
kubectl apply --server-side --force-conflicts -n "${ARGOCD_NAMESPACE}" -f "${ARGOCD_MANIFEST_URL}"

kubectl -n "${ARGOCD_NAMESPACE}" rollout status deployment/argocd-server --timeout=180s
kubectl -n "${ARGOCD_NAMESPACE}" rollout status deployment/argocd-repo-server --timeout=180s
kubectl -n "${ARGOCD_NAMESPACE}" rollout status statefulset/argocd-application-controller --timeout=180s

cat <<EOF

ArgoCD установлен в namespace ${ARGOCD_NAMESPACE}.

Следующие команды:

  kubectl -n ${ARGOCD_NAMESPACE} get pods
  kubectl -n ${ARGOCD_NAMESPACE} port-forward svc/argocd-server 8080:443
  kubectl -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
  kubectl apply -f platform/argocd/root-app.yaml

UI будет доступен локально по адресу:

  https://localhost:8080

EOF
