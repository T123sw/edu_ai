#!/usr/bin/env bash
# Activate the already built and validated preparation release.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_dir="$repo_root/frontend/dist-preparation-harness"
[[ -f "$release_dir/index.html" ]] || { echo 'Prepared frontend build is missing.' >&2; exit 1; }
[[ -f "$repo_root/frontend/dist/index.html" ]] || { echo 'Existing frontend is missing.' >&2; exit 1; }
if [[ $EUID -eq 0 ]]; then
  systemctl restart edu-ai-backend
else
  sudo systemctl restart edu-ai-backend
fi
ready=false
for attempt in $(seq 1 90); do
  if systemctl is-active --quiet edu-ai-backend && curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:8001/health >/dev/null; then
    ready=true
    break
  fi
  sleep 2
done
[[ "$ready" == true ]] || { echo 'Backend health check failed; frontend remains unchanged.' >&2; exit 1; }
# Keep old hashed assets usable by already-open browser tabs; publish index last.
cp -a "$release_dir/assets/." "$repo_root/frontend/dist/assets/"
if [[ -f "$release_dir/login-bg.png" ]]; then
  cp -a "$release_dir/login-bg.png" "$repo_root/frontend/dist/login-bg.png"
fi
cp -a "$release_dir/index.html" "$repo_root/frontend/dist/.index-preparation-next.html"
mv -f "$repo_root/frontend/dist/.index-preparation-next.html" "$repo_root/frontend/dist/index.html"
curl --noproxy '*' -fsS --max-time 5 http://127.0.0.1/backend/health
printf '\nPreparation release activated. Refresh the browser with Ctrl+Shift+R.\n'
