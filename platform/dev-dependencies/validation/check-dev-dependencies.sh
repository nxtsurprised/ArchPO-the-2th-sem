#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-databases}"

echo "== Kubernetes context =="
kubectl config current-context
kubectl cluster-info >/dev/null
echo

echo "== Namespace =="
kubectl get namespace "${NAMESPACE}"
echo

echo "== Pods =="
kubectl get pods -n "${NAMESPACE}" -o wide
echo

echo "== Services =="
kubectl get svc -n "${NAMESPACE}" -o wide
echo

echo "== Endpoints =="
kubectl get endpoints -n "${NAMESPACE}"
echo

echo "== Rollout status =="
kubectl -n "${NAMESPACE}" rollout status statefulset/postgres --timeout=180s
kubectl -n "${NAMESPACE}" rollout status statefulset/mongodb --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deployment/valkey --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deployment/minio --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deployment/chromadb --timeout=180s
echo

echo "== Expected DNS names =="
cat <<'EOF'
postgres.databases.svc.cluster.local:5432
mongodb.databases.svc.cluster.local:27017
mongo.databases.svc.cluster.local:27017
valkey.databases.svc.cluster.local:6379
redis.databases.svc.cluster.local:6379
minio.databases.svc.cluster.local:9000
chromadb.databases.svc.cluster.local:8000
chroma.databases.svc.cluster.local:8005
EOF
echo

echo "== App namespace quick view =="
kubectl get pods -n app || true
echo

cat <<'EOF'
Next app checks:
  kubectl describe pod -n app <pod>
  kubectl logs -n app deployment/auth-service
  kubectl logs -n app deployment/catalog-service
  kubectl logs -n app deployment/generation-service
  kubectl logs -n app deployment/workflow-service

Optional DNS check:
  kubectl apply -f platform/dev-dependencies/validation/dns-check-pod.yaml
  kubectl -n databases exec -it dns-check -- nslookup postgres.databases.svc.cluster.local
EOF
