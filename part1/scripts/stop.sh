#!/usr/bin/env bash
set -euo pipefail

TAG="latest"

while getopts ":t:" opt; do
  case "$opt" in
    t) TAG="$OPTARG" ;;
    *) echo "Usage: $0 -t <image-tag>" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"
COMPOSE_PROJECT_NAME=part1 APP_TAG="$TAG" docker compose down
