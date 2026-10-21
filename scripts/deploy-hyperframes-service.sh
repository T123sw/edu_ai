#!/usr/bin/env bash
# Activate the tested HyperFrames backend fix and retire its former sidecar.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo 'Run with sudo: system service configuration is owned by root.' >&2
  exit 1
fi
repo=/home/zxqs_ep/Edu_AI
backup=/etc/systemd/system/edu-ai-backend.service.before-hyperframes-$(date -u +%Y%m%dT%H%M%SZ)
cp -a /etc/systemd/system/edu-ai-backend.service "$backup"
install -m 0644 "$repo/deploy/systemd/edu-ai-backend.service" /etc/systemd/system/edu-ai-backend.service
systemctl daemon-reload
systemctl restart edu-ai-backend.service
for attempt in {1..60}; do
  if curl --fail --silent http://127.0.0.1:8001/openapi.json >/dev/null; then
    systemctl disable --now edu-ai-openmaic.service
    systemctl is-active edu-ai-backend.service
    echo "HyperFrames active; prior unit saved at $backup"
    exit 0
  fi
  sleep 1
done
echo "Backend did not become ready; inspect journalctl -u edu-ai-backend. Backup: $backup" >&2
exit 1
