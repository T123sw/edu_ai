#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON_BIN="${PYTHON:-python3}"
API_PORT="${API_PORT:-8001}"

"$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null
exec "$PYTHON_BIN" -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$API_PORT" \
  --reload \
  --reload-dir app \
  --reload-dir core
