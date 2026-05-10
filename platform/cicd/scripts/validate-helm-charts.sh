#!/usr/bin/env bash
set -euo pipefail

CHART_ROOT="${CHART_ROOT:-platform/helm}"
CHARTS=(
  auth-service
  catalog-service
  generation-service
  pmi-agent
)

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required" >&2
  exit 1
fi

for chart in "${CHARTS[@]}"; do
  chart_dir="${CHART_ROOT}/${chart}"
  echo "== helm lint ${chart_dir} =="
  helm lint "${chart_dir}"
  echo
  echo "== helm template ${chart} ${chart_dir} =="
  helm template "${chart}" "${chart_dir}" >/tmp/"${chart}".rendered.yaml
  echo "Rendered /tmp/${chart}.rendered.yaml"
  echo
done

echo "All Helm charts passed lint and template rendering."
