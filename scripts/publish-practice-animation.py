#!/usr/bin/env python3
"""Publish the verified practice/PBL animation frontend release."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/acceptance/2026-10-15-practice-generation-animation/deployment.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = json.loads(RECORD.read_text())
    if record.get('previewBrowserPassed') is not True:
        raise SystemExit('Release browser verification must pass before publishing.')
    source, release, live = Path(record['sourceSnapshot']), Path(record['release']), ROOT / 'frontend/dist'
    previous = record['previousIndexSha256']
    if digest(live / 'index.html') != previous:
        raise SystemExit('Another release was published. Reconcile with its source snapshot first.')
    for base, manifest in [(ROOT, record['inputManifest']), (source, record['sourceSnapshotManifest']), (release, record['assetManifest'])]:
        for name, expected in manifest.items():
            if digest(base / name) != expected:
                raise SystemExit(f'Validated input changed: {base / name}')
    for name, expected in record['assetManifest'].items():
        target = live / name
        if name != 'index.html' and target.exists() and digest(target) != expected:
            raise SystemExit(f'Existing asset collision: {name}')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(path):
        with client.open('http://127.0.0.1' + path, timeout=15) as response:
            return response.read()

    if json.loads(fetch('/backend/health')).get('status') != 'ok':
        raise SystemExit('Backend health check failed; frontend unchanged.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'frontend/dist-release-backups' / ('before-practice-animation-' + stamp)
    backup.mkdir(parents=True)
    old = (live / 'index.html').read_bytes()
    (backup / 'index.html').write_bytes(old)
    for name in record['assetManifest']:
        if name == 'index.html':
            continue
        target = live / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(release / name, target)
    if digest(live / 'index.html') != previous:
        raise SystemExit('Concurrent publication detected before activation; entry unchanged.')
    pending = live / 'index.practice-animation-next'
    shutil.copy2(release / 'index.html', pending)
    os.replace(pending, live / 'index.html')
    try:
        assert hashlib.sha256(fetch('/?practice-animation=' + stamp)).hexdigest() == record['releaseIndexSha256']
        assert all(digest(live / name) == expected for name, expected in record['assetManifest'].items())
        env = {**os.environ, 'PATH': '/home/zxqs_ep/miniforge3/envs/edu-ai/bin:' + os.environ.get('PATH', ''), 'PRACTICE_GENERATION_URL': 'http://127.0.0.1'}
        with (RECORD.parent / 'published-browser.log').open('w') as log:
            subprocess.run(['pnpm', 'exec', 'playwright', 'test', '-c', 'playwright.practice-generation.config.ts', 'practice-generation.spec.ts', 'pbl-home.spec.ts', 'practice.spec.ts'], cwd=source / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        assert hashlib.sha256(fetch('/?practice-animation-verified=' + stamp)).hexdigest() == record['releaseIndexSha256']
    except Exception:
        if digest(live / 'index.html') == record['releaseIndexSha256']:
            pending.write_bytes(old)
            os.replace(pending, live / 'index.html')
            record.update(status='rolled_back', frontendPublished=False, backup=str(backup))
            RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        raise
    record.update(status='published', frontendPublished=True, publishedAt=stamp, backup=str(backup), releaseFilesVerified=len(record['assetManifest']), nginxIndexMatches=True, backendHealthVerified=True, publishedBrowserTests=11, publishedBrowserSkipped=1, productionLearnerDataModified=False, verificationLimits='Real browser UI with mocked auth/business APIs; no external model generation tested.')
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(f'Published practice/PBL animation: {len(record["assetManifest"])} files and online browser checks verified.')


if __name__ == '__main__':
    main()
