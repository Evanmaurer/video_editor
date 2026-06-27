#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

check_node_version() {
  local version major minor
  version="$(node -p "process.versions.node")"
  major="$(node -p "process.versions.node.split('.')[0]")"
  minor="$(node -p "process.versions.node.split('.')[1]")"
  if [[ "$major" -eq 26 ]] || { [[ "$major" -eq 24 ]] && [[ "$minor" -ge 16 ]]; }; then
    echo "ERROR: Node.js ${version} breaks Electron postinstall (extract-zip)."
    echo "Use Node.js 22 LTS (see .node-version): https://github.com/electron/electron/issues/51619"
    exit 1
  fi
}

check_node_version

echo "==> Installing Node dependencies..."
if command -v pnpm &>/dev/null; then
  pnpm install
else
  npx pnpm@9 install
fi

echo "==> Validating Electron and pnpm configuration..."
node scripts/validate-electron-config.mjs --require-electron

echo "==> Setting up Python backend..."
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-dev.txt
echo "==> Verifying Python backend import..."
.venv/bin/python -c "import montage_backend; print('montage_backend OK')"
cd "$ROOT"

echo "==> Setup complete."
if ! command -v ffmpeg &>/dev/null || ! command -v ffprobe &>/dev/null; then
  echo ""
  echo "NOTE: FFmpeg is required for media import (proxy, thumbnail, waveform)."
  echo "Install with: brew install ffmpeg"
fi
echo "Run: pnpm dev"