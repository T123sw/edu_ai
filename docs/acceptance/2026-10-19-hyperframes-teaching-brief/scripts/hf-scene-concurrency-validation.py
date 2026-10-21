import json,time,shutil,threading
from pathlib import Path
from core.config import Config
from app.self_learning.service import gateway
from app.integrations.hyperframes.workflow_agent import NativeWorkflowAgent,WorkflowTools
from app.integrations.hyperframes.workflow_workers import WorkflowWorkers
rows=json.loads(Path('/tmp/hf-latest-analysis.json').read_text());source=Path(next(r for r in rows if r['spec']['node_id'].startswith('n3'))['workspace'])/'videos/bubble-sort-manual-trace'
root=Path('/home/zxqs_ep/data/main-review/hyperframes-teaching-brief-20261019/scene-comparison');root.mkdir(parents=True,exist_ok=True);results=[]
for cap in [4,6]:
 workspace=root/str(cap);project=workspace/'video';shutil.copytree(source,project,ignore=shutil.ignore_patterns('renders','exports','history','artifacts'),dirs_exist_ok=True)
 for path in (project/'.hyperframes').rglob('*'):
  if path.is_file() and path.suffix in ('.json','.md'):
   path.write_text(path.read_text().replace(str(source),str(project)))
 shutil.rmtree(project/'compositions/frames');(project/'compositions/frames').mkdir()
 runner=NativeWorkflowAgent(gateway('teacher'),workspace,lambda:None,timeout=1800)
 tools=WorkflowTools(workspace,lambda:None,runner=runner.run);tools.workers.close();tools.workers=WorkflowWorkers(workspace,runner.run,lambda:None,concurrency=cap,slots=threading.BoundedSemaphore(12))
 manifest=json.loads((project/'.hyperframes/host-scene-assets.json').read_text());ids=[p['frameId'] for p in manifest['packets'][:6]]
 try:
  start=time.time();out=tools.call('dispatch_frames',{'project_directory':str(project),'frame_ids':ids});assert out['ok'],out
  jobs=out['workers']
  while any(j['status'] in ('running','queued') for j in jobs):jobs=tools.workers.poll(wait_seconds=45)
  assert all(j['status']=='succeeded' for j in jobs),jobs
  row={'concurrency':cap,'seconds':round(time.time()-start,2),'workers':jobs,'frames':ids,'note':'Same six native scene packets; model calls are nondeterministic and share provider capacity with validation work.'}
  results.append(row);(root/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({'concurrency':cap,'seconds':row['seconds']}),flush=True)
 finally:tools.close()
