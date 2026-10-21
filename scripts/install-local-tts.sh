#!/usr/bin/env bash
# Install the reviewed local TTS unit and reload the backend deployment policy.
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ${EUID} -ne 0 ]]; then
  printf 'Run with administrator access: sudo bash %s\n' "$0" >&2
  exit 1
fi
[[ "$PROJECT_ROOT" == /home/zxqs_ep/Edu_AI ]] || {
  printf 'Adjust the deployment unit paths before installing on another host.\n' >&2
  exit 1
}
install -m 644 "$PROJECT_ROOT/deploy/systemd/edu-ai-tts.service" /etc/systemd/system/edu-ai-tts.service
install -m 644 "$PROJECT_ROOT/deploy/systemd/edu-ai-backend.service" /etc/systemd/system/edu-ai-backend.service
systemctl daemon-reload

# Retire only the known legacy Qwen service owned by the project user. Other
# listeners on 8188 are not killed; systemd will report a bind failure instead.
/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
import os
import pwd
import signal
import time
from pathlib import Path

uid = pwd.getpwnam('zxqs_ep').pw_uid
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    try:
        args = (entry / 'cmdline').read_bytes().split(b'\0')
        if (entry.stat().st_uid != uid
                or b'qwen_tts_server:app' not in args
                or b'8188' not in args
                or (entry / 'cwd').resolve() != Path('/home/zxqs_ep')):
            continue
        pid = int(entry.name)
        os.kill(pid, signal.SIGTERM)
        print(f'Stopping legacy Qwen service PID {pid}', flush=True)
        for _ in range(120):
            if not entry.exists():
                break
            time.sleep(1)
        else:
            raise SystemExit('Legacy TTS has not stopped; check it before continuing.')
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        continue
PY

systemctl enable --now edu-ai-tts.service
printf 'Waiting for the local TTS model to load...\n'
ready=false
for ((attempt=0; attempt<120; attempt++)); do
  if curl --noproxy '*' -fs --max-time 2 http://127.0.0.1:8188/health >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  journalctl -u edu-ai-tts.service -n 40 --no-pager
  exit 1
fi
systemctl restart edu-ai-backend.service
printf 'Waiting for the backend to start...\n'
for ((attempt=0; attempt<90; attempt++)); do
  if curl --noproxy '*' -fs --max-time 2 http://127.0.0.1:8001/health >/dev/null; then
    printf '\nLocal Qwen3-TTS and the backend are ready.\n'
    exit 0
  fi
  sleep 1
done
journalctl -u edu-ai-backend.service -n 40 --no-pager
exit 1
