"""Publish the verified task-center release after reloading its backend timestamps."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/acceptance/2026-10-15-task-center-cleanup/deployment.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = json.loads(RECORD.read_text())
    source, release, live = Path(record['sourceSnapshot']), Path(record['release']), ROOT / 'frontend/dist'
    for name, expected in {**record['sourceManifest'], **record['backendSourceManifest']}.items():
        if digest(ROOT / name) != expected:
            raise SystemExit(f'Source changed; reconcile before publishing: {name}')
    for name, expected in record['sourceManifest'].items():
        if digest(source / name) != expected:
            raise SystemExit(f'Prepared source changed: {name}')
    for name, expected in record['assetManifest'].items():
        if digest(release / name) != expected:
            raise SystemExit(f'Release changed: {name}')
    previous = digest(live / 'index.html')
    if previous not in {record['previousIndexSha256'], record['releaseIndexSha256']}:
        raise SystemExit('Another frontend release was published; rebuild on its source snapshot first.')
    if not record.get('prepublishBrowserPassed'):
        raise SystemExit('Prepublication browser verification is required.')
    if args.check:
        print('Source, release, browser checks and online baseline verified. Backend restart required before publishing.')
        return
    pid = int(subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'MainPID', '--value'], text=True))
    if not pid or pid == record['backendPidBefore']:
        raise SystemExit('Backend timestamp fields are not loaded. Run: sudo systemctl restart edu-ai-backend')
    age = int(subprocess.check_output(['ps', '-p', str(pid), '-o', 'etimes='], text=True).strip())
    if time.time() - age < max((ROOT / name).stat().st_mtime for name in record['backendSourceManifest']) - 2:
        raise SystemExit('Backend started before the verified changes. Restart it first.')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(path):
        with client.open('http://127.0.0.1' + path, timeout=10) as response:
            return response.read()

    deadline = time.monotonic() + 90
    while True:
        try:
            if json.loads(fetch('/backend/health')).get('status') == 'ok':
                break
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise SystemExit('Backend health did not recover; frontend unchanged.')
        time.sleep(2)
    if int(subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'MainPID', '--value'], text=True)) != pid:
        raise SystemExit('Backend process changed during verification; check service status.')
    if digest(live / 'index.html') != previous:
        raise SystemExit('Concurrent frontend publication detected; reconcile first.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'frontend/dist-release-backups' / f'before-task-center-{stamp}'
    backup.mkdir(parents=True, exist_ok=True)
    old = (live / 'index.html').read_bytes()
    (backup / 'index.html').write_bytes(old)
    for name in record['assetManifest']:
        if name == 'index.html':
            continue
        target = live / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(release / name, target)
    if digest(live / 'index.html') != previous:
        raise SystemExit('Concurrent publication before activation; entry unchanged.')
    pending = live / 'index.task-center-next'
    shutil.copy2(release / 'index.html', pending)
    os.replace(pending, live / 'index.html')
    try:
        assert hashlib.sha256(fetch('/?task-center=' + stamp)).hexdigest() == record['releaseIndexSha256']
        assert all(digest(live / name) == expected for name, expected in record['assetManifest'].items())
        env = {**os.environ, 'PROGRESS_FRONTEND_URL': 'http://127.0.0.1',
               'PATH': '/home/zxqs_ep/miniforge3/envs/edu-ai/bin:' + os.environ.get('PATH', '')}
        with (RECORD.parent / 'published-browser.log').open('w') as log:
            subprocess.run(['pnpm', 'exec', 'playwright', 'test', '-c', 'playwright.preparation-progress.config.ts',
                            'task-center.spec.ts', 'preparation-center-sync.spec.ts'],
                           cwd=source / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    except Exception:
        if digest(live / 'index.html') == record['releaseIndexSha256']:
            pending.write_bytes(old)
            os.replace(pending, live / 'index.html')
        raise
    record.update(status='published', blocker=None, frontendPublished=True, backendRestarted=True,
                  backendPidAfter=pid, publishedAt=stamp, backup=str(backup), nginxIndexMatches=True,
                  releaseFilesVerified=len(record['assetManifest']), onlineBrowserPassed=True)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print('Task center published; backend health, assets and desktop/mobile browser checks passed.')


if __name__ == '__main__':
    main()
