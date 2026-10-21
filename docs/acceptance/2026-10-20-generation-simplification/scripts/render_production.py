"""Isolated same-source, same-frame-rate native render comparison."""
import json,os,shlex,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
os.environ['PATH']=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH']
from app.integrations.hyperframes.workflow_agent import WorkflowTools
from app.integrations.hyperframes.runtime import RUNTIME
OUT=Path(__file__).resolve().parents[1];base=Path('/home/zxqs_ep/data/main-review/generation-simplification-20261020');source=base/'slow-video'
results=[]
for name,env in [('interleaved-production','HF_CAPTURE_PARALLEL_STREAM=true')]:
 workspace=base/name;project=workspace/'video';shutil.copytree(source,project,ignore=shutil.ignore_patterns('renders','exports','history','artifacts'),dirs_exist_ok=True)
 tools=WorkflowTools(workspace,lambda:None)
 try:
  command='cd '+shlex.quote(str(project))+' && '+env+' '+shlex.join([shutil.which('node'),str(RUNTIME/'node_modules/hyperframes/dist/cli.js'),'render','--quality','high','--workers','4','--fps','30','--output','renders/sample.mp4'])
  start=time.monotonic();r=tools.call('run_command',{'command':command});print(name,'started',r,flush=True)
  if not r.get('ok'):raise RuntimeError(r)
  while r.get('exit_code') is None:
   r=tools.call('poll_command',{'command_id':r['command_id'],'wait_seconds':45})
  row={'name':name,'seconds':time.monotonic()-start,'exit_code':r['exit_code'],'log':r['output_file'],'video':str(project/'renders/sample.mp4'),'fps':30,'note':'30 fps full production timeline, native interleaved scheduling'};results.append(row);print(json.dumps(row),flush=True)
  (OUT/'production-render.json').write_text(json.dumps(results,indent=2))
  shutil.copyfile(r['output_file'],OUT/(name+'-render.log'))
 finally:tools.close()
