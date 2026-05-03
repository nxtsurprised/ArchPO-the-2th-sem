#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_NAME="${RELEASE_NAME:-cilium}"
NAMESPACE="${NAMESPACE:-kube-system}"

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required. Install it from https://helm.sh/." >&2
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required." >&2
  exit 1
fi

helm repo add cilium https://helm.cilium.io/ >/dev/null
helm repo update cilium >/dev/null

helm upgrade --install "${RELEASE_NAME}" cilium/cilium \
  --namespace "${NAMESPACE}" \
  --values "${SCRIPT_DIR}/cilium-values.yaml" \
  --wait

kubectl -n "${NAMESPACE}" rollout status daemonset/cilium --timeout=300s
kubectl -n "${NAMESPACE}" rollout status deployment/cilium-operator --timeout=300s

if kubectl -n "${NAMESPACE}" get deployment hubble-relay >/dev/null 2>&1; then
  kubectl -n "${NAMESPACE}" rollout status deployment/hubble-relay --timeout=300s
fi

if kubectl -n "${NAMESPACE}" get deployment hubble-ui >/dev/null 2>&1; then
  kubectl -n "${NAMESPACE}" rollout status deployment/hubble-ui --timeout=300s
fi
