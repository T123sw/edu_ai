#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROJECT_ROOT
readonly STARTUP_TIMEOUT_SECONDS="${EDU_AI_STARTUP_TIMEOUT_SECONDS:-180}"
readonly SERVICES=(postgresql edu-ai-openmaic edu-ai-backend nginx)

if [[ "${EUID}" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

check_deployment_files() {
  local required_files=(
    "${PROJECT_ROOT}/.env"
    "${PROJECT_ROOT}/frontend/dist/index.html"
    "${PROJECT_ROOT}/openmaic-sidecar/.next/BUILD_ID"
  )
  local file

  for file in "${required_files[@]}"; do
    [[ -f "${file}" ]] || fail "required deployment file is missing: ${file}"
  done

  local env_mode
  env_mode="$(stat -c '%a' "${PROJECT_ROOT}/.env")"
  [[ "${env_mode}" == "600" ]] || fail ".env permissions must be 600 (current: ${env_mode})"
}

check_service_units() {
  local service
  for service in "${SERVICES[@]}"; do
    systemctl cat "${service}.service" >/dev/null 2>&1 \
      || fail "systemd unit is not installed: ${service}.service"
  done
}

wait_for_service() {
  local service="$1"
  local deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    if systemctl is-active --quiet "${service}"; then
      return 0
    fi
    if systemctl is-failed --quiet "${service}"; then
      fail "service entered failed state: ${service}"
    fi
    sleep 1
  done

  fail "service did not become active within ${STARTUP_TIMEOUT_SECONDS}s: ${service}"
}

wait_for_http() {
  local label="$1"
  local url="$2"
  local deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    if curl --noproxy 'localhost,127.0.0.1' \
      --fail --silent --max-time 5 --output /dev/null "${url}"; then
      printf '  [ok] %s\n' "${label}"
      return 0
    fi
    sleep 1
  done

  fail "health check did not pass within ${STARTUP_TIMEOUT_SECONDS}s: ${label}"
}

main() {
  [[ "${STARTUP_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]] \
    || fail "EDU_AI_STARTUP_TIMEOUT_SECONDS must be a positive integer"

  require_command systemctl
  require_command curl
  require_command stat
  if [[ "${EUID}" -ne 0 ]]; then
    require_command sudo
  fi

  check_deployment_files
  check_service_units

  printf 'Starting Edu-AI production services...\n'
  "${SUDO[@]}" systemctl start "${SERVICES[@]}"

  local service
  for service in "${SERVICES[@]}"; do
    wait_for_service "${service}"
    printf '  [active] %s\n' "${service}"
  done

  printf 'Checking application endpoints...\n'
  wait_for_http 'OpenMAIC' 'http://127.0.0.1:3000/api/health'
  wait_for_http 'FastAPI' 'http://127.0.0.1:8001/health'
  wait_for_http 'Nginx frontend/backend route' 'http://127.0.0.1/backend/health'

  printf 'Edu-AI is ready: http://127.0.0.1/\n'
}

main "$@"
