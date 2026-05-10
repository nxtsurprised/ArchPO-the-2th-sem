#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

kubectl delete -f "${ROOT_DIR}/platform/rate-limiting/envoyfilter-ratelimit.yaml" --ignore-not-found=true
kubectl delete namespace rate-limiting --ignore-not-found=true

echo "Rate limiting demo resources were removed. Istio was not removed."
