#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
REQUESTS="${REQUESTS:-12}"

echo "Sending ${REQUESTS} requests to ${GATEWAY_URL}/api/demo"
echo "The demo limit for PATH=/api/demo is 5 requests per minute."

for i in $(seq 1 "${REQUESTS}"); do
  code="$(curl -s -o /dev/null -w "%{http_code}" "${GATEWAY_URL}/api/demo" || true)"
  printf "%02d  %s\n" "${i}" "${code}"
done

cat <<'EOF'

Expected result:
  The first requests return 200, then later requests return 429.

If 429 does not appear:
  kubectl get pods -n rate-limiting
  kubectl logs -n rate-limiting deployment/ratelimit
  kubectl get envoyfilter -n istio-system
  istioctl proxy-status
  curl -i http://localhost:8080/api/demo

Wait a few seconds after applying EnvoyFilter because the ingress gateway needs to receive the new Envoy config.
EOF
