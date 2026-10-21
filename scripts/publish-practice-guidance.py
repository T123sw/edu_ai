"""Activate the verified guided-practice frontend after the backend reload."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/acceptance/2026-10-14-practice-guidance/deployment.json'
CLIENT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def get(path):
    with CLIENT.open('http://127.0.0.1' + path, timeout=30) as response:
        return response.read()


def main():
    record = json.loads(RECORD.read_text())
    paths = json.loads(get('/backend/openapi.json'))['paths']
    required = {
        '/api/practice/{identifier}/sessions': 'post',
        '/api/practice/{identifier}/sessions/{session_id}': 'get',
        '/api/practice/{identifier}/sessions/{session_id}/events': 'post',
    }
    if any(method not in paths.get(path, {}) for path, method in required.items()):
        raise SystemExit('Guided practice routes are not loaded. Restart edu-ai-backend first.')
    try:
        get('/backend/api/practice/release-probe/sessions/release-probe')
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise SystemExit(f'Unexpected session authentication status: {error.code}') from None
    else:
        raise SystemExit('Session access must require authentication.')
    if json.loads(get('/backend/health')).get('status') != 'ok':
        raise SystemExit('Backend health is not ok.')
    release, live = Path(record['release']), ROOT / 'frontend/dist'
    for name, expected in record['assetManifest'].items():
        if digest((release / name).read_bytes()) != expected:
            raise SystemExit(f'Prepared release changed: {name}')
        if name != 'index.html' and digest((live / name).read_bytes()) != expected:
            raise SystemExit(f'Staged asset changed: {name}')
    for name, expected in record['sourceManifest'].items():
        if digest((ROOT / name).read_bytes()) != expected:
            raise SystemExit(f'Guided practice source changed; revalidate before publication: {name}')
    previous = (live / 'index.html').read_bytes()
    expected = record['releaseIndexSha256']
    if digest(previous) not in {record['previousIndexSha256'], expected}:
        raise SystemExit('Another frontend release was published; reconcile the prepared release first.')
    pending = live / 'index.html.practice-guidance-next'
    shutil.copy2(release / 'index.html', pending)
    os.replace(pending, live / 'index.html')
    try:
        if digest(get('/')) != expected:
            raise RuntimeError('Nginx index does not match the release.')
    except Exception:
        pending.write_bytes(previous)
        os.replace(pending, live / 'index.html')
        raise
    record.update(frontendPublished=True, backendRoutesLoaded=True,
                  backendRestartRequired=False, nginxIndexMatches=True,
                  publishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
    record.pop('restartBlockedBy', None)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print('Guided practice frontend published; backend routes and authentication verified.')


if __name__ == '__main__':
    main()
