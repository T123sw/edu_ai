"""Publish the verified resource configuration UI after loading its backend changes."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/acceptance/2026-10-15-resource-config/deployment.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_for_backend(client, *, timeout_seconds=90):
    deadline = time.monotonic() + timeout_seconds
    last_error = 'not ready'
    while time.monotonic() < deadline:
        try:
            with client.open('http://127.0.0.1/backend/health',
                             timeout=min(5, max(.1, deadline - time.monotonic()))) as response:
                if json.load(response).get('status') == 'ok':
                    return
                last_error = 'health status is not ok'
        except urllib.error.HTTPError as error:
            if error.code not in {502, 503, 504}:
                raise SystemExit(f'Backend health check failed: HTTP {error.code}') from None
            last_error = f'HTTP {error.code}'
        except (OSError, urllib.error.URLError, ValueError) as error:
            last_error = type(error).__name__
        print(f'Waiting for backend startup ({last_error})…', flush=True)
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise SystemExit(f'Backend not ready after {timeout_seconds}s ({last_error}); frontend unchanged. Check: systemctl status edu-ai-backend')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate the prepared files without publishing')
    args = parser.parse_args()
    record = json.loads(RECORD.read_text())
    release = Path(record['release'])
    live = ROOT / 'frontend/dist'
    for relative, expected in {**record['sourceManifest'], **record['backendSourceManifest']}.items():
        if digest(ROOT / relative) != expected:
            raise SystemExit(f'Source changed since validation; reconcile first: {relative}')
    for relative, expected in record['assetManifest'].items():
        if digest(release / relative) != expected:
            raise SystemExit(f'Prepared release changed: {relative}')
    if digest(live / 'index.html') not in {record['previousIndexSha256'], record['releaseIndexSha256']}:
        raise SystemExit('Another frontend release was published; reconcile before publishing.')
    if args.check:
        print('Prepared source and release verified. Backend restart is required before publishing.')
        return
    pid = int(subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'MainPID', '--value'], text=True))
    if not pid or pid == record['backendPidBefore']:
        raise SystemExit('Backend changes are not loaded. Run: sudo systemctl restart edu-ai-backend')
    process_age = int(subprocess.check_output(['ps', '-p', str(pid), '-o', 'etimes='], text=True).strip())
    latest_change = max((ROOT / relative).stat().st_mtime for relative in record['backendSourceManifest'])
    if datetime.datetime.now().timestamp() - process_age < latest_change - 2:
        raise SystemExit('Backend started before the verified source changes. Restart it first.')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    wait_for_backend(client)
    if int(subprocess.check_output(['systemctl', 'show', 'edu-ai-backend', '-p', 'MainPID', '--value'], text=True)) != pid:
        raise SystemExit('Backend process changed during startup; check its status and rerun.')
    if digest(live / 'index.html') not in {record['previousIndexSha256'], record['releaseIndexSha256']}:
        raise SystemExit('Another frontend release was published while waiting; reconcile first.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'frontend/dist-release-backups' / f'resource-config-{stamp}'
    backup.mkdir(parents=True, exist_ok=True)
    previous = (live / 'index.html').read_bytes()
    (backup / 'index.html').write_bytes(previous)
    # Keep existing hashed assets for clients still running the previous entry.
    for relative in record['assetManifest']:
        if relative == 'index.html':
            continue
        target = live / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(release / relative, target)
    pending = live / 'index.resource-config-next'
    shutil.copy2(release / 'index.html', pending)
    os.replace(pending, live / 'index.html')
    try:
        with client.open('http://127.0.0.1/?resource-config=' + stamp, timeout=20) as response:
            assert hashlib.sha256(response.read()).hexdigest() == record['releaseIndexSha256']
        assert all(digest(live / relative) == expected for relative, expected in record['assetManifest'].items())
    except Exception:
        pending.write_bytes(previous)
        os.replace(pending, live / 'index.html')
        raise
    record.update(frontendPublished=True, backendRestarted=True, backendPidAfter=pid,
        nginxIndexMatches=True, releaseFilesVerified=len(record['assetManifest']), publishedAt=stamp, backup=str(backup))
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print('Resource configuration frontend published; backend restart verified.')


if __name__ == '__main__':
    main()
