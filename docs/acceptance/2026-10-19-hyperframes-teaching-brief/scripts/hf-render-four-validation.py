import json,os,shutil,subprocess,time
from pathlib import Path
from core.config import Config
from app.integrations.hyperframes.workflow_agent import WorkflowTools
rows=json.loads(Path('/tmp/hf-latest-analysis.json').read_text());source=Path(next(r for r in rows if r['spec']['node_id'].startswith('n1'))['workspace'])/'videos/bubble-sort-core'
root=Path('/home/zxqs_ep/data/main-review/hyperframes-teaching-brief-20261019/render-comparison');root.mkdir(parents=True,exist_ok=True)
results=[]
for workers in [2,4]:
 workspace=root/str(workers);project=workspace/'video';shutil.copytree(source,project,ignore=shutil.ignore_patterns('renders','exports','history','artifacts'),dirs_exist_ok=True)
 os.environ['HYPERFRAMES_RENDER_WORKERS']=str(workers)
 tools=WorkflowTools(workspace,lambda:None)
 try:
  start=time.time();r=tools.call('render_project',{'project_directory':str(project)})
  while r.get('ok') and r.get('exit_code') is None:
   r=tools.call('poll_command',{'command_id':r['command_id']})
  if not r.get('ok') or r.get('exit_code')!=0:raise RuntimeError(str(r))
  video=project/'renders/video.mp4'
  subprocess.run(['/usr/bin/ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  result={'workers':workers,'seconds':round(time.time()-start,2),'video':str(video),'log':r.get('output_file'),'summary':r['output'][-1400:]};results.append(result)
  (root/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({'workers':workers,'seconds':result['seconds']}),flush=True)
 finally:tools.close()
