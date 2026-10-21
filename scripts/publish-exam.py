"""Publish the prepared exam UI only after the matching backend is activated."""
import hashlib,json,shutil,subprocess,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/acceptance/2026-10-17-exam-e2e-fixes'
RELEASE=Path('/tmp/edu-exam-fixes-release');LIVE=ROOT/'frontend/dist'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    record=json.loads((OUT/'release.json').read_text())
    # Read-only checks precede every publication.
    schema=json.load(urllib.request.urlopen('http://127.0.0.1:8001/openapi.json',timeout=15))
    assert 'get' in schema['paths'].get('/api/exam-generations',{}),'Restart the main backend first'
    assert '/api/exam-generations/{generation_id}/paper' in schema['paths'],'Paper endpoint not loaded'
    health=json.load(urllib.request.urlopen('http://127.0.0.1:8026/health',timeout=5))
    assert health['status']=='ok','DeepTutor not ready'
    for name,value in record['sourceManifest'].items():
        assert digest(ROOT/name)==value,'Source changed; rebuild: '+name
    for name,value in record['assetManifest'].items():
        assert digest(RELEASE/name)==value,'Release changed: '+name
    assert digest(LIVE/'index.html') in [record['previousIndexSha256'],record['releaseIndexSha256']],'Another frontend release has been published; reconcile it first'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'frontend/dist-release-backups'/('before-exam-'+stamp)
    shutil.copytree(LIVE,backup,symlinks=True)
    # Install immutable assets first, then atomically replace the entry point.
    for source in RELEASE.rglob('*'):
        if not source.is_file() or source.name=='index.html':continue
        target=LIVE/source.relative_to(RELEASE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    temporary=LIVE/'index.exam.tmp';shutil.copy2(RELEASE/'index.html',temporary);temporary.replace(LIVE/'index.html')
    served=urllib.request.urlopen('http://127.0.0.1/',timeout=10).read()
    assert hashlib.sha256(served).hexdigest()==record['releaseIndexSha256']
    record.update(status='published',backup=str(backup),publishedAt=stamp)
    (OUT/'release.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print('Exam UI published and Nginx entry verified.')
if __name__=='__main__':main()
