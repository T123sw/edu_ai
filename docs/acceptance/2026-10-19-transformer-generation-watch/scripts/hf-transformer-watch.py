import os,json,time,sys
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from core.config import Config
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from app.database.models import CoursePreparationRecord as P,CoursePreparationAttemptRecord as A,PreparationArtifact as R,PreparationExecution as E,DurableTaskModel as T,CoursePreparationEventRecord as V
PID='prep_65488c25779346448e1dcbe0b809d73e'
out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-19-transformer-generation-watch');out.mkdir(exist_ok=True)
engine=create_engine(os.environ['DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on -c statement_timeout=10000'})
base=Path(os.environ['COURSE_STORAGE_ROOT'])/'hyperframes/workflows'
known={};last=''
def save(path,value):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str));tmp.replace(path)
def sample():
 global known
 now=time.time()
 with Session(engine) as s:
  p=s.get(P,PID);a=s.get(A,(PID,p.current_attempt_no));e=s.get(E,(PID,p.current_attempt_no));c=e.checkpoint
  save(out/'plan.json',c.get('plan',{}));save(out/'brief.json',c.get('brief',{}))
  rows=list(s.scalars(select(R).where(R.preparation_id==PID).order_by(R.created_at)))
  tasks={t.task_id:t for t in s.scalars(select(T).where(T.scope_id==PID,T.task_id.like('generate_%')))}
  events=[{'sequence':v.sequence,'type':v.event_type,'at':v.occurred_at.isoformat(),'payload':v.payload} for v in s.scalars(select(V).where(V.preparation_id==PID).order_by(V.sequence))]
  save(out/'preparation-events.json',events)
  snapshot={'at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':round(now-p.created_at.timestamp(),2),'preparation_id':PID,'status':a.status,'stage':a.stage,'error':e.error_code,'delivery':c.get('partial_delivery'),'resource_counts':dict(Counter(r.status for r in rows)),'planned_resources':len(c.get('resource_specs',[])),'artifacts':[]}
  for r in rows:
   dest=out/r.artifact_id;dest.mkdir(exist_ok=True)
   body=r.content or {};state=((body.get('_native_generation') or {}).get('value') or {}).get('state',{})
   if state.get('workspace_key'):known[r.artifact_id]=str(base/state['workspace_key'])
   if state.get('teaching_brief'):save(dest/'teaching-brief.json',state['teaching_brief'])
   if r.status=='draft':save(dest/'content.json',body)
   t=tasks.get('generate_'+r.artifact_id)
   row={'id':r.artifact_id,'node':r.spec['node_id'],'title':r.spec['title'],'type':r.resource_type,'status':r.status,'error':r.error_code,'created_at':r.created_at.isoformat(),'elapsed_since_submission':round(now-r.created_at.timestamp(),2)}
   if t:row.update(task_status=t.status,worker=t.lease_owner,attempts=t.attempt_count,started_at=t.started_at,finished_at=t.finished_at,execution_seconds=round((t.finished_at or now)-t.started_at,2) if t.started_at else None,progress=t.progress,task_error=t.error)
   if r.artifact_id in known:
    ws=Path(known[r.artifact_id]);row['workspace']=str(ws)
    fp=ws/'.host/events.jsonl';ev=[]
    if fp.exists():
     for line in fp.read_text().splitlines():
      try:ev.append(json.loads(line))
      except json.JSONDecodeError:pass
    row['tool_calls']=len(ev);row['tool_failures']=[v for v in ev if not v.get('ok',True)];row['last_tool']=ev[-1] if ev else None
    workers=[]
    for f in (ws/'.host/workers').glob('*.json'):
     try:d=json.loads(f.read_text());workers.append({k:d.get(k) for k in ['worker_id','status','submitted_at','started_at','finished_at','error']})
     except (ValueError,OSError):pass
    row['scene_workers']=workers
    projects=[]
    for f in (ws/'videos').glob('*/BRIEF.md'):
     project=f.parent;meta=project/'audio_meta.json';req=project/'audio_request.json'
     v={'path':str(project),'brief':f.read_text(),'files':[x.name for x in project.iterdir() if x.is_file()],'frame_files':len(list((project/'compositions/frames').glob('*.html'))),'renders':[{'name':x.name,'size':x.stat().st_size} for x in (project/'renders').glob('*.mp4')]}
     if meta.exists():
      try:m=json.loads(meta.read_text());v['audio_lines']=len(m.get('voices',[]));v['audio_seconds']=sum(q.get('duration_s',0) for q in m.get('voices',[]))
      except ValueError:pass
     if req.exists():
      try:v['narration_chars']=sum(len(q.get('text','')) for q in json.loads(req.read_text()).get('lines',[]))
      except ValueError:pass
     projects.append(v)
    row['projects']=projects
    if (dest/'teaching-brief.json').exists():
     b=json.loads((dest/'teaching-brief.json').read_text());row['brief_decisions']=b['decisions'];row['brief_seconds']=b['seconds']
    save(dest/'host-events.json',ev)
   snapshot['artifacts'].append(row)
  save(out/'latest.json',snapshot)
  with (out/'snapshots.jsonl').open('a') as f:f.write(json.dumps(snapshot,ensure_ascii=False,default=str)+'\n')
  return snapshot
while True:
 try:
  snap=sample();short={'at':snap['at'],'minutes':round(snap['elapsed_seconds']/60,1),'status':snap['status'],'stage':snap['stage'],'counts':snap['resource_counts'],'available':(snap['delivery'] or {}).get('available_resources'),'videos':[{'node':r['node'],'status':r['status'],'tools':r.get('tool_calls',0),'tool_errors':len(r.get('tool_failures',[])),'workers':dict(Counter(w['status'] for w in r.get('scene_workers',[]))),'brief_minutes':r.get('brief_decisions',{}).get('target_minutes'),'projects':[{'audio_seconds':p.get('audio_seconds'),'frames':p['frame_files'],'renders':p['renders']} for p in r.get('projects',[])]} for r in snap['artifacts'] if r['type']=='classroom']}
  print(json.dumps(short,ensure_ascii=False),flush=True)
  if '--once' in sys.argv or snap['status'] in ('succeeded','failed','canceled'):break
 except Exception as exc:print(json.dumps({'observer_error':type(exc).__name__,'message':str(exc)[:200]}),flush=True)
 time.sleep(30)
