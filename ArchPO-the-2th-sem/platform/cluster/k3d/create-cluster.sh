#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-archpo-local}"
CONFIG_FILE="${SCRIPT_DIR}/cluster.yaml"

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d is required. Install it from https://k3d.io/." >&2
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required." >&2
  exit 1
fi

if k3d cluster get "${CLUSTER_NAME}" >/dev/null 2>&1; then
  echo "k3d cluster '${CLUSTER_NAME}' already exists."
else
  k3d cluster create --config "${CONFIG_FILE}"
fi

kubectl config use-context "k3d-${CLUSTER_NAME}"
kubectl get nodes
