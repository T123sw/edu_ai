#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.example and configure it first." >&2
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm was not found. Activate the edu-ai Conda environment first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "==> Check native HyperFrames runtime"
python "$REPO_ROOT/scripts/check-hyperframes.py"

echo "==> Build production frontend"
pnpm --dir "$REPO_ROOT/frontend" build

echo "Production builds completed."
