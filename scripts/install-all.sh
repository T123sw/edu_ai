#!/usr/bin/env bash
set -euo pipefail

SKIP_PYTHON=0
SKIP_NODE=0
SKIP_OPTIONAL=0
SKIP_PLAYWRIGHT_BROWSERS=0
SKIP_ENV_FILES=0
INCLUDE_RAG_STANDALONE=0
PYTHON_BIN="${PYTHON:-python3}"

for arg in "$@"; do
  case "$arg" in
    --skip-python) SKIP_PYTHON=1 ;;
    --skip-node) SKIP_NODE=1 ;;
    --skip-optional) SKIP_OPTIONAL=1 ;;
    --skip-playwright-browsers) SKIP_PLAYWRIGHT_BROWSERS=1 ;;
    --skip-env-files) SKIP_ENV_FILES=1 ;;
    --include-rag-standalone) INCLUDE_RAG_STANDALONE=1 ;;
    --python=*) PYTHON_BIN="${arg#--python=}" ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/Edu_AI"
BACKEND_DIR="$FRONTEND_DIR/api/Edu_AI"
HTML2PPT_DIR="$BACKEND_DIR/html2ppt"
DOM_TO_PPTX_DIR="$HTML2PPT_DIR/dom-to-pptx"
AI_LECTURER_DIR="$BACKEND_DIR/AI_Lecturer"
RAG_STANDALONE_DIR="$BACKEND_DIR/rag_v2/rag-main"
EDU_AGENT_DIR="$REPO_ROOT/EduAgent"

step() {
  echo
  echo "==> $1"
}

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' was not found in PATH." >&2
    exit 1
  fi
}

copy_if_missing() {
  local source="$1"
  local destination="$2"

  if [[ ! -f "$source" ]]; then
    echo "Skip missing template: $source"
    return
  fi

  if [[ -e "$destination" ]]; then
    echo "Keep existing file: $destination"
    return
  fi

  cp "$source" "$destination"
  echo "Created: $destination"
}

echo "Edu-AI dependency installer"
echo "Repository: $REPO_ROOT"

if [[ "$SKIP_PYTHON" -eq 0 ]]; then
  need_command "$PYTHON_BIN"
  step "Upgrade pip tooling"
  "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel

  step "Install backend Python dependencies"
  "$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements_api.txt"

  if [[ "$SKIP_OPTIONAL" -eq 0 ]]; then
    step "Install AI Lecturer offline-video Python dependencies"
    "$PYTHON_BIN" -m pip install -r "$AI_LECTURER_DIR/requirements-offline-py312.txt"

    step "Install EduAgent Python dependencies"
    "$PYTHON_BIN" -m pip install -r "$EDU_AGENT_DIR/requirements.txt"
  fi

  if [[ "$INCLUDE_RAG_STANDALONE" -eq 1 ]]; then
    step "Install standalone RAG Python dependencies"
    "$PYTHON_BIN" -m pip install -r "$RAG_STANDALONE_DIR/requirements.txt"
  fi

  if [[ "$SKIP_PLAYWRIGHT_BROWSERS" -eq 0 ]]; then
    step "Install Playwright Chromium browser"
    "$PYTHON_BIN" -m playwright install chromium
  fi
fi

if [[ "$SKIP_NODE" -eq 0 ]]; then
  need_command npm
  step "Install frontend Node dependencies"
  npm ci --prefix "$FRONTEND_DIR"

  step "Install html2ppt service Node dependencies"
  npm ci --prefix "$HTML2PPT_DIR"

  step "Install dom-to-pptx Node dependencies"
  npm ci --prefix "$DOM_TO_PPTX_DIR"
fi

if [[ "$SKIP_ENV_FILES" -eq 0 ]]; then
  step "Create local env/config files when missing"
  copy_if_missing "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
  copy_if_missing "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  copy_if_missing "$HTML2PPT_DIR/.env.example" "$HTML2PPT_DIR/.env"
  copy_if_missing "$EDU_AGENT_DIR/config.toml.example" "$EDU_AGENT_DIR/config.toml"
fi

echo
echo "Dependency installation finished."
echo "Next: fill local .env/config.toml files with real API keys and machine-specific paths."
