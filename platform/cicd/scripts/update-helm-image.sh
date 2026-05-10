#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <service> <image-repository> <image-tag>" >&2
  exit 1
fi

SERVICE="$1"
REPOSITORY="$2"
TAG="$3"
CHART_DIR="platform/helm/${SERVICE}"
VALUES_FILE="${CHART_DIR}/values.yaml"

if [[ ! -d "${CHART_DIR}" ]]; then
  echo "Helm chart not found: ${CHART_DIR}" >&2
  exit 1
fi

if [[ ! -f "${VALUES_FILE}" ]]; then
  echo "values.yaml not found: ${VALUES_FILE}" >&2
  exit 1
fi

if command -v yq >/dev/null 2>&1; then
  export REPOSITORY TAG
  yq -i '.image.repository = strenv(REPOSITORY) | .image.tag = strenv(TAG)' "${VALUES_FILE}"
else
  python3 - "$VALUES_FILE" "$REPOSITORY" "$TAG" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
repository = sys.argv[2]
tag = sys.argv[3]
lines = path.read_text().splitlines()

out = []
in_image = False
for line in lines:
    stripped = line.strip()
    if line.startswith("image:"):
        in_image = True
        out.append(line)
        continue
    if in_image and line and not line.startswith(" "):
        in_image = False
    if in_image and stripped.startswith("repository:"):
        indent = line[: len(line) - len(line.lstrip())]
        out.append(f'{indent}repository: "{repository}"')
        continue
    if in_image and stripped.startswith("tag:"):
        indent = line[: len(line) - len(line.lstrip())]
        out.append(f'{indent}tag: "{tag}"')
        continue
    out.append(line)

path.write_text("\n".join(out) + "\n")
PY
fi

echo "Updated ${VALUES_FILE}:"
grep -A 4 '^image:' "${VALUES_FILE}"
