#!/usr/bin/env python3
"""Publish the backward-compatible three-page UI from its verified snapshot."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/'docs/acceptance/2026-10-15-experiment-pages/deployment.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 r=json.loads(RECORD.read_text());release=Path(r['release']);source=Path(r['sourceSnapshot']);live=ROOT/'frontend/dist'
 for group,base in [('inputManifest',ROOT),('backendSourceManifest',ROOT),('sourceManifest',source),('assetManifest',release)]:
  for name,h in r[group].items():
   if sha(base/name)!=h:raise SystemExit(f'{group} changed: {name}')
 old=(live/'index.html').read_bytes();previous=sha(live/'index.html')
 if previous not in [r['previousIndexSha256'],r['releaseIndexSha256']]:raise SystemExit('Concurrent release detected; rebuild against current source snapshot.')
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 backup=ROOT/'frontend/dist-release-backups'/f'before-experiment-pages-{stamp}';backup.mkdir(parents=True,exist_ok=True);(backup/'index.html').write_bytes(old)
 for name in r['assetManifest']:
  if name=='index.html':continue
  p=live/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(release/name,p)
 if sha(live/'index.html')!=previous:raise SystemExit('Concurrent release before activation; entry unchanged.')
 pending=live/'index.pages-next';shutil.copy2(release/'index.html',pending);os.replace(pending,live/'index.html')
 try:
  client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with client.open('http://127.0.0.1/?experiment-pages='+stamp,timeout=15) as response:
   assert hashlib.sha256(response.read()).hexdigest()==r['releaseIndexSha256']
  assert all(sha(live/name)==h for name,h in r['assetManifest'].items())
  env={**os.environ,'EXPERIMENT_PUBLISHED_URL':'http://127.0.0.1','PATH':'/home/zxqs_ep/miniforge3/envs/edu-ai/bin:'+os.environ.get('PATH','')}
  with (RECORD.parent/'published-browser.log').open('w') as log:
   subprocess.run(['pnpm','exec','playwright','test','-c','playwright.pages-publish.config.ts'],cwd=source/'frontend',env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=200)
 except Exception:
  if sha(live/'index.html')==r['releaseIndexSha256']:pending.write_bytes(old);os.replace(pending,live/'index.html')
  raise
 r.update(status='published' if r.get('backendRestarted') else 'frontend-published-awaiting-backend',frontendPublished=True,backup=str(backup),publishedAt=stamp,releaseFilesVerified=len(r['assetManifest']),nginxIndexMatches=True,onlineBrowserPassed=True)
 RECORD.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('Frontend published and online browser checks passed.')
if __name__=='__main__':main()
