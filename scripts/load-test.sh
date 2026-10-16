#!/usr/bin/env bash
# Controlled load generator for HPA demo.
# Usage: ./scripts/load-test.sh [target-url] [requests]
# Example: ./scripts/load-test.sh http://taskboard.local/api/tasks 500
set -euo pipefail
URL="${1:-http://localhost:8000/api/tasks}"
N="${2:-500}"
echo "Hitting $URL $N times..."
for i in $(seq 1 "$N"); do
  curl -s -o /dev/null "$URL" &
  if (( i % 50 == 0 )); then wait; echo "  $i/$N"; fi
done
wait
echo "Done. Watch: kubectl get hpa -n taskboard -w"
