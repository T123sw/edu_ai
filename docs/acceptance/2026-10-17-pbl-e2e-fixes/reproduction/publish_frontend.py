from pathlib import Path
import hashlib,json,shutil,os,time,urllib.request,datetime
root=Path('/home/zxqs_ep/Edu_AI');live=root/'frontend/dist';release=Path('/tmp/edu-pbl-fixes-release');source=Path('/tmp/edu-pbl-fixes-source');out=root/'docs/acceptance/2026-10-17-pbl-e2e-fixes'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline='a1eb03976f5758ff1746fba4e4258e7ada20e982a10ed384766dbbd3b9b351ee'
assert sha(live/'index.html')==baseline,'Concurrent release: rebuild on the new published snapshot'
changed=['frontend/src/practice/PracticeGenerationProgress.tsx','frontend/src/pbl/projectTypes.ts','frontend/src/pbl/ProjectChecks.tsx']
for name in changed:assert sha(root/name)==sha(source/name),name
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=root/'frontend/dist-release-backups'/('before-pbl-e2e-fixes-'+stamp);shutil.copytree(live,backup)
manifest={str(p.relative_to(release)):sha(p) for p in release.rglob('*') if p.is_file()}
for name in manifest:
 if name=='index.html':continue
 target=live/name;target.parent.mkdir(exist_ok=True,parents=True)
 if target.exists() and sha(target)==manifest[name]:continue
 pending=target.with_name(target.name+'.pbl-fixes-pending');shutil.copy2(release/name,pending);os.replace(pending,target)
assert sha(live/'index.html')==baseline
pending=live/'index.pbl-fixes-pending';shutil.copy2(release/'index.html',pending);os.replace(pending,live/'index.html')
try:
 client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 served=client.open('http://127.0.0.1/?pbl-fixes='+str(time.time()),timeout=30).read()
 assert hashlib.sha256(served).hexdigest()==manifest['index.html']
 assert all(sha(live/name)==digest for name,digest in manifest.items())
except Exception:
 shutil.copy2(backup/'index.html',pending);os.replace(pending,live/'index.html');raise
record={'status':'frontend_published_backend_restart_pending','publishedAt':stamp,'sourceSnapshot':str(source),'release':str(release),'backup':str(backup),'previousIndexSha256':baseline,'releaseIndexSha256':manifest['index.html'],'inputManifest':{name:sha(root/name) for name in changed},'assetManifest':manifest,'filesVerified':len(manifest),'nginxIndexVerified':True,'backendRestartRequired':True}
(out/'deployment.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print('Published and verified',len(manifest),'files',flush=True)
