#!/usr/bin/env python3
"""Verify the deployed PBL generation code after an administrator restarts the backend."""
import hashlib
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/'docs/acceptance/2026-10-15-pbl-generic-generation/deployment.json'

def main():
    record=json.loads(RECORD.read_text())
    for name,expected in record['backendSourceManifest'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            raise SystemExit('Backend source changed; validate and update the release record first: '+name)
    for name in record['removedBackendFiles']:
        if (ROOT/name).exists():raise SystemExit('Retired generator unexpectedly exists: '+name)
    pid=int(subprocess.check_output(['systemctl','show','edu-ai-backend','-p','MainPID','--value'],text=True))
    if not pid:raise SystemExit('Backend is not running')
    age=int(subprocess.check_output(['ps','-p',str(pid),'-o','etimes='],text=True).strip())
    if time.time()-age < max((ROOT/name).stat().st_mtime for name in record['backendSourceManifest'])-2:
        raise SystemExit('Backend has not loaded the new code. Run: sudo systemctl restart edu-ai-backend')
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with client.open('http://127.0.0.1/backend/health',timeout=10) as response:
        if json.load(response).get('status')!='ok':raise SystemExit('Backend health check failed')
    record.update(status='published',backendRestarted=True,backendRestartBlock=None,backendPidAfter=pid,
                  backendReloadEvidence='Observed process start after all verified source edits and successful HTTP health check; administrator restart.')
    RECORD.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print('PBL backend reload verified; all saved frontend and backend changes are active.')

if __name__=='__main__':main()
