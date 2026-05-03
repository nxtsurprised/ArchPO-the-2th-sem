#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-archpo-local}"

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d is required. Install it from https://k3d.io/." >&2
  exit 1
fi

if k3d cluster get "${CLUSTER_NAME}" >/dev/null 2>&1; then
  k3d cluster delete "${CLUSTER_NAME}"
else
  echo "k3d cluster '${CLUSTER_NAME}' does not exist."
fi
