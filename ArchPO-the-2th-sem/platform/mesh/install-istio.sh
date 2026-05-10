#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VALUES_FILE="${ROOT_DIR}/platform/mesh/istio-values.yaml"

echo "Checking Kubernetes API access..."
kubectl cluster-info >/dev/null

if ! command -v istioctl >/dev/null 2>&1; then
  cat <<'EOF'
istioctl is not installed.

Install Istio CLI first, then re-run this script.

macOS with Homebrew:
  brew install istioctl

Manual install:
  curl -L https://istio.io/downloadIstio | sh -
  export PATH="$PWD/istio-*/bin:$PATH"

Validation after installation:
  istioctl version
EOF
  exit 1
fi

echo "Creating istio-system namespace if needed..."
kubectl create namespace istio-system --dry-run=client -o yaml | kubectl apply -f -

echo "Installing Istio from ${VALUES_FILE}..."
istioctl install -f "${VALUES_FILE}" -y

echo "Waiting for Istio control plane and ingress gateway..."
kubectl rollout status deployment/istiod -n istio-system --timeout=180s
kubectl rollout status deployment/istio-ingressgateway -n istio-system --timeout=180s

cat <<'EOF'

Istio is installed.

Validation commands:
  kubectl get pods -n istio-system
  istioctl proxy-status

Local gateway check after deploying the demo:
  kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:80
  curl -i http://localhost:8080/api/demo
EOF
