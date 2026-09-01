#!/usr/bin/env bash
set -euo pipefail

SKIP_BROWSERS=0
SKIP_ENV_FILE=0

for arg in "$@"; do
  case "$arg" in
    --skip-browsers) SKIP_BROWSERS=1 ;;
    --skip-env-file) SKIP_ENV_FILE=1 ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
ENVIRONMENT_FILE="$REPO_ROOT/environment.yml"
ENV_TEMPLATE="$REPO_ROOT/.env.example"
ENV_FILE="$REPO_ROOT/.env"

if ! command -v conda >/dev/null 2>&1; then
  echo "Conda was not found. Install Miniforge first, then rerun this script." >&2
  exit 1
fi

echo "==> Create or update the edu-ai Conda environment"
conda env update --name edu-ai --file "$ENVIRONMENT_FILE" --prune

run_in_env() {
  conda run --no-capture-output --name edu-ai "$@"
}

echo "==> Install OpenMAIC dependencies"
run_in_env pnpm --dir "$REPO_ROOT/openmaic-sidecar" install --frozen-lockfile

echo "==> Install frontend dependencies"
run_in_env pnpm --dir "$REPO_ROOT/frontend" install --frozen-lockfile

if [[ "$SKIP_BROWSERS" -eq 0 ]]; then
  echo "==> Install Playwright Chromium binaries"
  run_in_env pnpm --dir "$REPO_ROOT/openmaic-sidecar" exec playwright install chromium
  run_in_env pnpm --dir "$REPO_ROOT/frontend" exec playwright install chromium
fi

if [[ "$SKIP_ENV_FILE" -eq 0 && ! -e "$ENV_FILE" ]]; then
  cp "$ENV_TEMPLATE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "==> Created $ENV_FILE; fill in secrets before starting services"
fi

echo "Installation complete. Run scripts/build-production.sh inside the edu-ai environment next."
