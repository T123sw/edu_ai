"""Publish the verified exam preview fix over the exact current release."""
import hashlib
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/zxqs_ep/Edu_AI')
OUT = ROOT / 'docs/acceptance/2026-10-18-exam-preview-fix'
RELEASE = Path('/tmp/edu-exam-preview-fix-release')
LIVE = ROOT / 'frontend/dist'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = json.loads((OUT / 'release.json').read_text())
    assert json.loads((OUT / 'preview-browser.json').read_text())['passed']
    assert '# fail 0' in (OUT / 'unit-tests.txt').read_text()
    assert not (OUT / 'lint.txt').read_text().strip()
    assert not (OUT / 'typecheck.txt').read_text().strip()
    for name, digest in record['sourceManifest'].items():
        assert sha(ROOT / name) == digest
        assert sha(Path(record['sourceSnapshot']) / name) == digest
    assert sha(LIVE / 'index.html') == record['previousIndexSha256'], 'Reconcile intervening deployment first'
    health = json.load(urllib.request.urlopen('http://127.0.0.1:8026/health', timeout=10))
    assert health['status'] == 'ok'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'frontend/dist-release-backups' / ('before-exam-preview-' + stamp)
    shutil.copytree(LIVE, backup, symlinks=True)
    assets = {str(p.relative_to(RELEASE)): sha(p) for p in RELEASE.rglob('*') if p.is_file()}
    for name in assets:
        if name == 'index.html':
            continue
        target = LIVE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RELEASE / name, target)
    temporary = LIVE / 'index.exam-preview.tmp'
    shutil.copy2(RELEASE / 'index.html', temporary)
    temporary.replace(LIVE / 'index.html')
    for name, digest in assets.items():
        assert sha(LIVE / name) == digest
    served = urllib.request.urlopen('http://127.0.0.1/', timeout=10).read()
    assert hashlib.sha256(served).hexdigest() == assets['index.html']
    record.update(status='published', publishedAt=stamp, backup=str(backup), release=str(RELEASE),
                  releaseIndexSha256=assets['index.html'], assetManifest=assets)
    (OUT / 'release.json').write_text(json.dumps(record, indent=2) + '\n')
    print('Published exam preview fix; served entry and all release files verified.')


if __name__ == '__main__':
    main()
