#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-observability}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need kubectl

echo "== Namespace =="
kubectl get namespace "${NAMESPACE}"

echo
echo "== Pods =="
kubectl get pods -n "${NAMESPACE}" -o wide

echo
echo "== Services =="
kubectl get svc -n "${NAMESPACE}"

echo
echo "== Rollout status =="
for deploy in prometheus alertmanager loki tempo otel-collector grafana; do
  kubectl -n "${NAMESPACE}" rollout status "deployment/${deploy}" --timeout=120s
done
kubectl -n "${NAMESPACE}" rollout status daemonset/promtail --timeout=120s

tmp_dir="$(mktemp -d)"
cleanup() {
  if [[ -n "${prometheus_pf_pid:-}" ]]; then kill "${prometheus_pf_pid}" >/dev/null 2>&1 || true; fi
  if [[ -n "${loki_pf_pid:-}" ]]; then kill "${loki_pf_pid}" >/dev/null 2>&1 || true; fi
  if [[ -n "${tempo_pf_pid:-}" ]]; then kill "${tempo_pf_pid}" >/dev/null 2>&1 || true; fi
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

echo
echo "== Local readiness probes =="
if command -v curl >/dev/null 2>&1; then
  kubectl -n "${NAMESPACE}" port-forward svc/prometheus 19090:9090 >"${tmp_dir}/prometheus.log" 2>&1 &
  prometheus_pf_pid="$!"
  kubectl -n "${NAMESPACE}" port-forward svc/loki 13100:3100 >"${tmp_dir}/loki.log" 2>&1 &
  loki_pf_pid="$!"
  kubectl -n "${NAMESPACE}" port-forward svc/tempo 13200:3200 >"${tmp_dir}/tempo.log" 2>&1 &
  tempo_pf_pid="$!"
  sleep 3

  curl -fsS http://localhost:19090/-/ready >/dev/null && echo "Prometheus ready"
  curl -fsS http://localhost:13100/ready >/dev/null && echo "Loki ready"
  curl -fsS http://localhost:13200/ready >/dev/null && echo "Tempo ready"

  echo
  echo "Prometheus active targets:"
  curl -fsS http://localhost:19090/api/v1/targets \
    | sed 's/},{/},\n{/g' \
    | grep -E '"job"|"health"' \
    | head -n 40 || true
else
  echo "curl is not installed; skipped HTTP readiness and Prometheus targets checks."
fi

echo
echo "== Useful port-forward commands =="
cat <<EOF
kubectl -n ${NAMESPACE} port-forward svc/grafana 3000:3000
kubectl -n ${NAMESPACE} port-forward svc/prometheus 9090:9090
kubectl -n ${NAMESPACE} port-forward svc/alertmanager 9093:9093
kubectl -n ${NAMESPACE} port-forward svc/loki 3100:3100
kubectl -n ${NAMESPACE} port-forward svc/tempo 3200:3200
EOF
