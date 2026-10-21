"""Publish the verified statement UI and check whether model instructions are loaded."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time,urllib.request
ROOT=Path(__file__).resolve().parents[2]
RECORD=ROOT/'docs/acceptance/2026-10-15-pbl-model-statement/deployment.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 record=json.loads(RECORD.read_text());release=Path(record['release']);live=ROOT/'frontend/dist'
 for name,item in record['sourceManifest'].items():
  assert sha(ROOT/name)==item['new'],('Source changed',name)
 for name,digest in record['assetManifest'].items():
  assert sha(release/name)==digest,('Release changed',name)
 assert sha(live/'index.html') in [record['previousIndexSha256'],record['releaseIndexSha256']],'Concurrent release; reconcile first'
 pid=int(subprocess.check_output(['systemctl','show','edu-ai-backend','-p','MainPID','--value'],text=True))
 age=int(subprocess.check_output(['ps','-p',str(pid),'-o','etimes='],text=True).strip()) if pid else 0
 changed=max((ROOT/name).stat().st_mtime for name in record['sourceManifest'] if name.startswith('backend/'))
 loaded=bool(pid and pid!=record['backendPidBefore'] and time.time()-age>=changed-2)
 client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 if loaded:
  health=json.loads(client.open('http://127.0.0.1/backend/health',timeout=20).read())
  assert health.get('status')=='ok','Backend health check failed; wait for startup and retry'
 # The UI restoration is independently deployable; report prompts as pending until restart.
 previous=(live/'index.html').read_bytes()
 for name in record['assetManifest']:
  if name=='index.html':continue
  target=live/name;target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists() and sha(target)==record['assetManifest'][name]:continue
  pending=target.with_name(target.name+'.pbl-pending');shutil.copy2(release/name,pending);os.replace(pending,target)
 assert sha(live/'index.html') in [record['previousIndexSha256'],record['releaseIndexSha256']]
 pending=live/'index.pbl-pending';shutil.copy2(release/'index.html',pending);os.replace(pending,live/'index.html')
 try:
  served=client.open('http://127.0.0.1/?pbl-statement='+str(time.time()),timeout=20).read()
  assert hashlib.sha256(served).hexdigest()==record['releaseIndexSha256']
  assert all(sha(live/name)==digest for name,digest in record['assetManifest'].items())
 except Exception:
  pending.write_bytes(previous);os.replace(pending,live/'index.html');raise
 record.update(frontendPublished=True,nginxIndexMatches=True,backendRestarted=loaded,backendPidAfter=pid,newGenerationPromptsLoaded=loaded,releaseFilesVerified=len(record['assetManifest']))
 if not loaded:record['backendReloadBlocker']='sudo -n systemctl restart edu-ai-backend: a password is required'
 else:record.pop('backendReloadBlocker',None)
 RECORD.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 print('Frontend published and verified. Model prompt reload: '+('verified' if loaded else 'pending; run sudo systemctl restart edu-ai-backend, then rerun this script.'))
if __name__=='__main__':main()
