#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
REQUESTS="${REQUESTS:-20}"

echo "Sending ${REQUESTS} requests to ${GATEWAY_URL}/api/demo"
for i in $(seq 1 "${REQUESTS}"); do
  code="$(curl -s -o /dev/null -w "%{http_code}" "${GATEWAY_URL}/api/demo" || true)"
  printf "%02d  %s\n" "${i}" "${code}"
done

cat <<EOF

Useful checks:
  kubectl get pods -n traffic-demo
  kubectl get destinationrule,virtualservice,gateway -n traffic-demo
  istioctl proxy-status
  kubectl logs -n istio-system deployment/istio-ingressgateway --tail=80

To introduce demo faults:
  kubectl apply -f platform/mesh/traffic-demo/fault-injection.yaml
  ./platform/mesh/traffic-demo/load-test.sh

To remove the fault injection:
  kubectl apply -f platform/mesh/traffic-demo/virtualservice.yaml
EOF
