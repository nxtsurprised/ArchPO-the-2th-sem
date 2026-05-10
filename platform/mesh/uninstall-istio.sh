#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Removing Block 3 demo resources if they exist..."
kubectl delete -f "${ROOT_DIR}/platform/rate-limiting/envoyfilter-ratelimit.yaml" --ignore-not-found=true || true
kubectl delete -f "${ROOT_DIR}/platform/ingress/pdb.yaml" --ignore-not-found=true || true
kubectl delete namespace traffic-demo --ignore-not-found=true
kubectl delete namespace rate-limiting --ignore-not-found=true

if ! command -v istioctl >/dev/null 2>&1; then
  echo "istioctl is not installed. Install it to uninstall Istio cleanly."
  exit 1
fi

echo "Uninstalling Istio..."
istioctl uninstall --purge -y
kubectl delete namespace istio-system --ignore-not-found=true

echo "Istio and Block 3 demo resources were removed. Other platform namespaces were not touched."
