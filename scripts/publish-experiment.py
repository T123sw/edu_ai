#!/usr/bin/env python3
"""Publish the verified experiment release after the backend has been restarted."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/acceptance/2026-10-15-experiment-skill/deployment.json'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    record=json.loads(RECORD.read_text());release=Path(record['release']);source=Path(record['sourceSnapshot']);live=ROOT/'frontend/dist'
    for name,expected in record['inputManifest'].items():
        if digest(ROOT/name)!=expected:raise SystemExit(f'Source changed; reconcile before publishing: {name}')
    for name,expected in record['sourceManifest'].items():
        if digest(source/name)!=expected:raise SystemExit(f'Prepared source changed: {name}')
    for name,expected in record['assetManifest'].items():
        if digest(release/name)!=expected:raise SystemExit(f'Release changed: {name}')
    previous=digest(live/'index.html')
    if previous not in [record['previousIndexSha256'],record['releaseIndexSha256']]:raise SystemExit('Another release was published. Rebuild on its source snapshot; do not overwrite it.')
    if args.check:
        print('Source, isolated release and live baseline verified. Restart the backend, then run this script without --check.');return
    pid=int(subprocess.check_output(['systemctl','show','edu-ai-backend','-p','MainPID','--value'],text=True))
    if not pid or pid==record['backendPidBefore']:raise SystemExit('Backend has not reloaded the experiment APIs. Run: sudo systemctl restart edu-ai-backend')
    age=int(subprocess.check_output(['ps','-p',str(pid),'-o','etimes='],text=True).strip())
    if time.time()-age < max((ROOT/f).stat().st_mtime for f in record['backendSourceManifest'])-2:raise SystemExit('Backend started before the verified changes; restart it first.')
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def fetch(path):
        with client.open('http://127.0.0.1'+path,timeout=10) as response:return response.read()
    deadline=time.monotonic()+90
    while True:
        try:
            if json.loads(fetch('/backend/health')).get('status')=='ok':break
        except (OSError,ValueError):pass
        if time.monotonic()>=deadline:raise SystemExit('Backend health did not become ready; frontend unchanged.')
        time.sleep(2)
    paths=json.loads(fetch('/backend/openapi.json'))['paths']
    required=['/api/practice/{identifier}/experiment/runs','/api/practice/{identifier}/experiment/runs/latest','/api/practice/{identifier}/experiment/runs/{run_id}/teaching-context','/api/practice/{identifier}/experiment/teaching-context/{context_id}/evidence']
    if not all(p in paths for p in required):raise SystemExit('New experiment APIs are not loaded; frontend unchanged.')
    for path in ['/backend/api/practice','/backend/api/practice/release-check/experiment/runs/latest']:
        try:fetch(path)
        except urllib.error.HTTPError as exc:
            if exc.code not in [401,403]:raise SystemExit(f'Authentication check failed: {path} HTTP {exc.code}')
        else:raise SystemExit('Unauthenticated private experiment endpoint unexpectedly accessible')
    if digest(live/'index.html')!=previous:raise SystemExit('Concurrent frontend release detected; reconcile first.')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=ROOT/'frontend/dist-release-backups'/f'before-experiment-{stamp}';backup.mkdir(parents=True,exist_ok=True)
    old=(live/'index.html').read_bytes();(backup/'index.html').write_bytes(old)
    for name in record['assetManifest']:
        if name=='index.html':continue
        target=live/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(release/name,target)
    if digest(live/'index.html')!=previous:raise SystemExit('Concurrent publication before activation; entry unchanged.')
    pending=live/'index.experiment-next';shutil.copy2(release/'index.html',pending);os.replace(pending,live/'index.html')
    try:
        assert hashlib.sha256(fetch('/?experiment-release='+stamp)).hexdigest()==record['releaseIndexSha256']
        assert all(digest(live/name)==expected for name,expected in record['assetManifest'].items())
        env={**os.environ,'EXPERIMENT_PUBLISHED_URL':'http://127.0.0.1','PATH':'/home/zxqs_ep/miniforge3/envs/edu-ai/bin:'+os.environ.get('PATH','')}
        with (RECORD.parent/'published-browser.log').open('w') as log:
            subprocess.run(['pnpm','exec','playwright','test','-c','playwright.experiment-publish.config.ts'],cwd=source/'frontend',env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    except Exception:
        if digest(live/'index.html')==record['releaseIndexSha256']:
            pending.write_bytes(old);os.replace(pending,live/'index.html')
        raise
    record.update(status="published",blocker=None,frontendPublished=True,backendRestarted=True,backendPidAfter=pid,publishedAt=stamp,backup=str(backup),nginxIndexMatches=True,releaseFilesVerified=len(record['assetManifest']),onlineBrowserPassed=True,backendRoutesAndAuthVerified=True)
    RECORD.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print('Experiment release published. Backend routes, authentication, assets and online browser checks passed.')

if __name__=='__main__':main()
