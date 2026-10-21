"""Activate the prepared tutor release only after the backend serves its routes.

Run after the administrator restarts edu-ai-backend. No service privileges needed.
The recorded index hashes protect against overwriting another release.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / 'docs/acceptance/2026-10-14-pbl-tutor/deployment.json'
ORIGIN = 'http://127.0.0.1'
client = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path):
    with client.open(ORIGIN + path, timeout=20) as response:
        return response.read()


def main():
    record = json.loads(RECORD.read_text())
    schema = json.loads(get('/backend/openapi.json'))
    route = schema.get('paths', {}).get('/api/pbl/{identifier}/tutor', {})
    if not {'get', 'post'} <= set(route):
        raise SystemExit('Backend tutor routes are not loaded. Administrator restart still required.')
    # Verify the real public route is mounted and still enforces authentication.
    try:
        get('/backend/api/pbl/release-probe/tutor?artifactVersion=1&taskId=probe')
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise SystemExit(f'Unexpected tutor route status: {error.code}') from None
    else:
        raise SystemExit('Tutor endpoint did not require authentication; release halted.')
    release = Path(record['release'])
    live = ROOT / 'frontend/dist'
    expected = record['releaseIndexSha256']
    if hashlib.sha256((release / 'index.html').read_bytes()).hexdigest() != expected:
        raise SystemExit('Prepared release changed; review it before publishing.')
    before = hashlib.sha256((live / 'index.html').read_bytes()).hexdigest()
    if before not in {record['previousIndexSha256'], expected}:
        raise SystemExit('Another frontend release was published; reconcile before publishing.')
    for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', (release / 'index.html').read_text()):
        if not get(asset):
            raise SystemExit(f'Release asset unavailable: {asset}')
    next_index = live / 'index.html.pbl-tutor-next'
    shutil.copy2(release / 'index.html', next_index)
    os.replace(next_index, live / 'index.html')
    if hashlib.sha256(get('/')).hexdigest() != expected:
        raise SystemExit('Nginx index differs from the release; inspect the deployment before continuing.')
    pid = int(subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '--property=MainPID', '--value'], text=True))
    record.update(frontendPublished=True, backendRestarted=pid != record['backendPidBefore'],
                  backendPidAfter=pid, tutorRoutesLoaded=True, tutorUnauthenticatedStatus=401,
                  nginxIndexMatches=True, publishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
    record.pop('restartBlockedBy', None)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'frontendPublished': True, 'tutorRoutesLoaded': True, 'backendPid': pid}, ensure_ascii=False))


if __name__ == '__main__':
    main()
