#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/apps/backend"
TOKEN="${MONTAGE_AUTH_TOKEN:-montage-dev-token}"

echo "Stopping stale processes on ports 8000 and 5173..."
for port in 8000 5173; do
  pid="$(lsof -ti :"$port" 2>/dev/null || true)"
  if [[ -n "$pid" ]]; then
    kill $pid 2>/dev/null || true
  fi
done
sleep 1

echo "Starting backend on http://127.0.0.1:8000 ..."
cd "$BACKEND_DIR"
MONTAGE_PORT=8000 MONTAGE_AUTH_TOKEN="$TOKEN" .venv/bin/python -m montage_backend.main &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8000/health" | grep -q media_library; then
    echo "Backend ready."
    break
  fi
  sleep 0.5
done

export PATH="/opt/homebrew/opt/node@22/bin:${PATH:-}"
export MONTAGE_AUTO_SPAWN=false
export MONTAGE_AUTH_TOKEN="$TOKEN"
unset ELECTRON_RUN_AS_NODE

cd "$ROOT"
pnpm dev
