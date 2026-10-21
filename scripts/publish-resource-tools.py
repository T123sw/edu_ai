"""Activate the verified resource tools release after the backend is restarted."""
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

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/acceptance/2026-10-14-podcast-scenario-flashcards/deployment.json'
CLIENT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(path):
    with CLIENT.open('http://127.0.0.1' + path, timeout=30) as response:
        return response.read()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    record = json.loads(RECORD.read_text())
    schema = json.loads(get('/backend/openapi.json'))
    audio = '/api/personal-studio/resources/podcast/{material_id}/audio'
    if 'get' not in schema.get('paths', {}).get(audio, {}):
        raise SystemExit('Backend podcast route is not loaded. Restart edu-ai-backend first.')
    request = schema['paths']['/api/personal-studio/generate']['post']['requestBody']['content']['application/json']['schema']
    model = schema['components']['schemas'][request['$ref'].split('/')[-1]]
    kinds = set(model['properties']['resource_type']['enum'])
    if kinds != {'report', 'quiz', 'flashcard', 'graph', 'podcast', 'scenario'}:
        raise SystemExit('Backend resource types do not match the prepared release.')
    try:
        get('/backend/api/personal-studio/resources/podcast/release-probe/audio')
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise SystemExit(f'Unexpected private audio status: {error.code}') from None
    else:
        raise SystemExit('Private audio must require authentication.')
    release, live = Path(record['release']), ROOT / 'frontend/dist'
    for name, expected in record['assetManifest'].items():
        if digest((release / name).read_bytes()) != expected:
            raise SystemExit(f'Prepared release changed: {name}')
        if name != 'index.html' and digest((live / name).read_bytes()) != expected:
            raise SystemExit(f'Staged asset changed: {name}')
    previous = (live / 'index.html').read_bytes()
    expected = record['releaseIndexSha256']
    if digest(previous) not in {record['previousIndexSha256'], expected}:
        raise SystemExit('Another frontend release was published; reconcile before continuing.')
    for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', (release / 'index.html').read_text()):
        if digest(get(asset)) != record['assetManifest'][asset.lstrip('/')]:
            raise SystemExit(f'Nginx asset mismatch: {asset}')
    health = json.loads(get('/backend/health'))
    if health.get('status') != 'ok':
        raise SystemExit('Backend health is not ok.')
    pending = live / 'index.html.resource-tools-next'
    shutil.copy2(release / 'index.html', pending)
    os.replace(pending, live / 'index.html')
    try:
        if digest(get('/')) != expected:
            raise RuntimeError('Nginx index does not match the release.')
    except Exception:
        pending.write_bytes(previous)
        os.replace(pending, live / 'index.html')
        raise
    pid = int(subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'MainPID', '--value'], text=True))
    record.update(frontendPublished=True, backendRestarted=pid != record['backendPidBefore'],
                  backendPidAfter=pid, podcastRouteLoaded=True, audioUnauthenticatedStatus=401,
                  nginxIndexMatches=True, productionHealth=health.get('status'),
                  publishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
    record.pop('restartBlockedBy', None)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'frontendPublished': True, 'backendPid': pid, 'activeTools': sorted(kinds)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
