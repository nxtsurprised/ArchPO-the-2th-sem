#!/usr/bin/env bash
set -euo pipefail

kubectl delete namespace traffic-demo --ignore-not-found=true
echo "traffic-demo namespace removed."
