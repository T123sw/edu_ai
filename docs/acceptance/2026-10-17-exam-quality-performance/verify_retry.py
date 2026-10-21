"""Real PDF -> upload API -> durable worker -> MinerU -> DeepTutor -> private DB.
Production settings are read before persistence isolation; credentials never exported.
"""
import os,json,time,socket,secrets,subprocess,threading,hashlib
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
WORK=ROOT/'.runtime/exam-real-paper-e2e'
from core.config import Config
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
os.environ['PYTHON_DOTENV_DISABLED']='1'
from app.exam_generation.snapshots import SnapshotCodec
import sys,sqlite3
resume=json.loads(Path(sys.argv[1]).read_text())
owner=resume['owner']
codec=SnapshotCodec()
with sqlite3.connect(Path(resume['run_directory'])/'state.db') as previous_db:
 previous_row=json.loads(previous_db.execute("select payload from app_state_records where namespace='exam_generation_v1' and record_key=?",(resume['generation_id'],)).fetchone()[0])
frozen=previous_row['encrypted_snapshot']
codec.capture=lambda actor: frozen if actor==owner else (_ for _ in ()).throw(PermissionError())
run=Path(resume['run_directory'])
for key in list(os.environ):
 if key.endswith('_PERSISTENCE_MODE'):os.environ[key]='json'
os.environ.update(DATABASE_URL='sqlite:///'+str(run/'state.db'),JOB_PERSISTENCE_MODE='json',APP_STATE_PERSISTENCE_MODE='json',MATERIAL_PERSISTENCE_MODE='json',COURSE_STORAGE_ROOT=str(run/'courses'))
for key,name in {'STORAGE_ROOT':'app','RUNTIME_CONFIG_ROOT':'config','VECTOR_DB_PATH':'vectors','DOCUMENT_INDEX_PATH':'documents.json','DOCUMENTS_ROOT':'documents','VIDEOS_ROOT':'videos','VIDEO_CHUNKS_ROOT':'chunks','TEMP_DIR':'temp'}.items():
 value=run/name;os.environ[key]=str(value);setattr(Config,key,value)
from sqlalchemy import create_engine
from app.database.models import AppStateRecord
engine=create_engine(os.environ['DATABASE_URL']);AppStateRecord.__table__.create(engine,checkfirst=True)
from app.exam_generation.repository import GenerationRepository
from app.exam_generation.service import ExamGenerationHandler
from app.chat.tasks.task_store import TaskStore,get_task_store
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.durable_task_executor import DurableTaskExecutor
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import get_job
from app.services.personal_knowledge_service import PersonalKnowledgeService
from app.services import knowledge_document_service
from app.api import exam_generations as api
from app.auth import get_current_user
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
blocked=[]
def forbidden(*a,**k):
 blocked.append('unexpected_knowledge_ingestion');raise AssertionError('Unexpected knowledge ingestion')
PersonalKnowledgeService.create_document=forbidden
PersonalKnowledgeService.submit_index=forbidden
knowledge_document_service.submit_index_job=forbidden
network=[]
original_send=httpx.Client.send
async_send=httpx.AsyncClient.send
def check_url(request):
 if request.url.port==8189 or '/embeddings' in request.url.path:forbidden()
 network.append({'method':request.method,'host':request.url.host,'port':request.url.port,'path':request.url.path})
def send(self,request,*a,**k):check_url(request);return original_send(self,request,*a,**k)
async def asend(self,request,*a,**k):check_url(request);return await async_send(self,request,*a,**k)
httpx.Client.send=send;httpx.AsyncClient.send=asend
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
token=secrets.token_urlsafe(40)
os.environ.update(EDU_DEEPTUTOR_URL=f'http://127.0.0.1:{port}',EDU_DEEPTUTOR_TOKEN=token)
env={**os.environ,'DEEPTUTOR_HOME':str(run/'deeptutor')};env.pop('PYTHONPATH',None)
log=(run/'service-retry.log').open('w');service=ROOT/'services/deeptutor'
process=subprocess.Popen([str(service/'.venv/bin/python'),'-m','uvicorn','edu_deeptutor.api:create_app','--factory','--host','127.0.0.1','--port',str(port)],cwd=service,env=env,stdout=log,stderr=subprocess.STDOUT)
summary={'boundary':'isolated storage; real upload/generation APIs, durable executor, MinerU and model; local authentication overridden','owner':owner,'run_directory':str(run),'source_sha256':hashlib.sha256((WORK/'source.pdf').read_bytes()).hexdigest(),'timeline':[],'production_business_writes':False}
tasks=None
try:
 for _ in range(120):
  if process.poll() is not None:raise RuntimeError('Service exited')
  try:
   if httpx.get(f'http://127.0.0.1:{port}/health',timeout=1,trust_env=False).status_code==200:break
  except httpx.HTTPError:pass
  time.sleep(.25)
 else:raise RuntimeError('Service startup timeout')
 tasks=TaskStore(str(run/'tasks.db'))
 app=FastAPI();app.include_router(api.router)
 app.dependency_overrides[get_current_user]=lambda:{'username':owner}
 app.dependency_overrides[api.snapshot_codec]=lambda:codec
 app.dependency_overrides[get_task_store]=lambda:tasks
 registry=DurableTaskHandlerRegistry();registry.register('exam_generate',1,ExamGenerationHandler(codec=codec))
 executor=DurableTaskExecutor(task_store=tasks,handler_registry=registry,completion_service=JobCompletionService(task_store=tasks),lease_seconds=60,heartbeat_interval=10)
 with TestClient(app) as client:
  started=time.monotonic()
  from app.services.job_retry_service import retry_durable_job
  from app.exam_generation.repository import identifier
  from uuid import uuid5,NAMESPACE_URL
  retried=retry_durable_job(get_job(resume['generation_id']),owner_user_id=owner,task_store=tasks)
  assert retried is not None
  gid=identifier(owner,str(uuid5(NAMESPACE_URL,retried.edu_job_id)))
  summary['generation_id']=gid;summary['retry_job_id']=retried.edu_job_id
  summary['retry_of']=resume['generation_id']
  before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (run/'deeptutor/edu_checkpoints').rglob('*.json')}
  worker=threading.Thread(target=executor.run_once,daemon=True);worker.start()
  while worker.is_alive():
   response=client.get('/api/exam-generations/'+gid)
   if response.status_code==404:
    worker.join(timeout=.25);continue
   status=response.json()
   if not summary['timeline'] or status['message']!=summary['timeline'][-1]['message'] or status['status']!=summary['timeline'][-1]['status']:
    summary['timeline'].append({'seconds':round(time.monotonic()-started,2),**status});print(json.dumps(summary['timeline'][-1],ensure_ascii=False),flush=True)
   (OUT/'isolated-retry.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
   if time.monotonic()-started>1800:tasks.request_cancel(retried.edu_job_id,owner_user_id=owner)
   worker.join(timeout=2)
  summary['seconds']=round(time.monotonic()-started,2)
  summary['final']=client.get('/api/exam-generations/'+gid).json()
  row=GenerationRepository().get(owner,gid)
  (run/'retry-record.json').write_text(json.dumps({k:v for k,v in row.items() if k!='encrypted_snapshot'},ensure_ascii=False,indent=2))
  job=get_job(retried.edu_job_id);summary['error_code']=job.error_code
  if row.get('parsed_sources'):
   summary['parsed']=[{'parser':s['parser'],'characters':len(s['content']),'layout_blocks':len(s['content_list']),'image_count':len(s['images'])} for s in row['parsed_sources']]
  if row.get('blueprint'):
   (run/'blueprint.json').write_text(json.dumps(row['blueprint'],ensure_ascii=False,indent=2))
  if row.get('result'):
   (run/'retry-result.json').write_text(json.dumps(row['result'],ensure_ascii=False,indent=2))
   meta=row['result'].get('metadata',{});s=meta.get('summary',{})
   summary['generation_summary']={k:v for k,v in s.items() if k in ('success','source','requested','template_count','completed','failed')}
   summary['usage_summary']=next((e['metadata'].get('usage_summary') for e in row['events'] if e['type']=='done'),None)
  after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (run/'deeptutor/edu_checkpoints').rglob('*.json')}
  summary['accepted_checkpoints_preserved']=all(after.get(k)==v for k,v in before.items())
  summary['reused_checkpoint_count']=len(before)
  summary['knowledge_ingestion_blocked_calls']=len(blocked)
  summary['embedding_calls']=sum('/embeddings' in c['path'] or c['port']==8189 for c in network)
  summary['network']=network
  (OUT/'isolated-retry.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
  print('FINAL',summary['final'],flush=True)
finally:
 process.terminate()
 try:process.wait(timeout=15)
 except subprocess.TimeoutExpired:process.kill();process.wait()
 log.close()
 if tasks:tasks.close()
 engine.dispose()
