"""Real PDF -> upload API -> durable worker -> MinerU -> DeepTutor -> private DB.
Production settings are read before persistence isolation; credentials never exported.
"""
import os,json,time,socket,secrets,subprocess,threading,hashlib
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(os.environ.get('EXAM_EVIDENCE_OUT',str(Path(__file__).resolve().parent)))
WORK=ROOT/'.runtime/exam-real-paper-e2e'
from core.config import Config
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
os.environ['PYTHON_DOTENV_DISABLED']='1'
from app.exam_generation.snapshots import SnapshotCodec
owner='exam-isolated-'+uuid4().hex[:12]
codec=SnapshotCodec();frozen=codec.capture(owner)
codec.capture=lambda actor: frozen if actor==owner else (_ for _ in ()).throw(PermissionError())
run=WORK/('isolated-'+uuid4().hex[:8]);run.mkdir(mode=0o700)
for key in list(os.environ):
 if key.endswith('_PERSISTENCE_MODE'):os.environ[key]='json'
os.environ.update(DATABASE_URL='sqlite:///'+str(run/'state.db'),JOB_PERSISTENCE_MODE='json',APP_STATE_PERSISTENCE_MODE='json',MATERIAL_PERSISTENCE_MODE='json',COURSE_STORAGE_ROOT=str(run/'courses'))
for key,name in {'STORAGE_ROOT':'app','RUNTIME_CONFIG_ROOT':'config','VECTOR_DB_PATH':'vectors','DOCUMENT_INDEX_PATH':'documents.json','DOCUMENTS_ROOT':'documents','VIDEOS_ROOT':'videos','VIDEO_CHUNKS_ROOT':'chunks','TEMP_DIR':'temp'}.items():
 value=run/name;os.environ[key]=str(value);setattr(Config,key,value)
from sqlalchemy import create_engine
from app.database.models import AppStateRecord
engine=create_engine(os.environ['DATABASE_URL']);AppStateRecord.__table__.create(engine)
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
env={**os.environ,'DEEPTUTOR_HOME':str(run/'deeptutor')};env['PYTHONPATH']=str(ROOT/'.runtime/exam-quality-v7/bridge5/src')+':'+str(ROOT/'.runtime/exam-quality-v7/bridge5/.upstream/DeepTutor')
log=(run/'service.log').open('w');service=ROOT/'.runtime/exam-quality-v7/bridge5'
process=subprocess.Popen([str(ROOT/'services/deeptutor/.venv/bin/python'),'-m','uvicorn','edu_deeptutor.api:create_app','--factory','--host','127.0.0.1','--port',str(port)],cwd=service,env=env,stdout=log,stderr=subprocess.STDOUT)
summary={'boundary':'isolated storage; real upload/generation APIs, durable executor, MinerU and model; local authentication overridden','owner':owner,'run_directory':str(run),'source_sha256':hashlib.sha256((WORK/'source.pdf').read_bytes()).hexdigest(),'timeline':[],'production_business_writes':False,'candidate_patch':__import__('json').loads((service/'upstream.lock.json').read_text())['patches']}
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
  response=client.post('/api/exam-generations/documents',files={'file':('USTC-2017-data-structures.pdf',(WORK/'source.pdf').read_bytes(),'application/pdf')})
  assert response.status_code==201,response.text
  summary['upload_http']=response.status_code;doc=response.json()['document_id']
  payload={'request_id':str(uuid4()),'mode':'mimic','language':'zh','requirement':'依据整份原卷生成一套新的数据结构模拟试卷，保持原题顺序、题型和对应考点，保留子题结构，使用新的数据或情境，不照抄原题。','sources':[{'document_id':doc,'role':'template'}]}
  response=client.post('/api/exam-generations',json=payload);assert response.status_code==202,response.text
  summary['create_http']=202;gid=response.json()['generation_id'];summary['generation_id']=gid
  worker=threading.Thread(target=executor.run_once,daemon=True);worker.start()
  while worker.is_alive():
   status=client.get('/api/exam-generations/'+gid).json()
   if not summary['timeline'] or status['message']!=summary['timeline'][-1]['message'] or status['status']!=summary['timeline'][-1]['status']:
    summary['timeline'].append({'seconds':round(time.monotonic()-started,2),**status});print(json.dumps(summary['timeline'][-1],ensure_ascii=False),flush=True)
   (OUT/'isolated.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
   if time.monotonic()-started>1800:tasks.request_cancel(gid,owner_user_id=owner)
   worker.join(timeout=2)
  summary['seconds']=round(time.monotonic()-started,2)
  summary['final']=client.get('/api/exam-generations/'+gid).json()
  row=GenerationRepository().get(owner,gid)
  (run/'record.json').write_text(json.dumps({k:v for k,v in row.items() if k!='encrypted_snapshot'},ensure_ascii=False,indent=2))
  job=get_job(gid);summary['error_code']=job.error_code
  if row.get('parsed_sources'):
   summary['parsed']=[{'parser':s['parser'],'characters':len(s['content']),'layout_blocks':len(s['content_list']),'image_count':len(s['images'])} for s in row['parsed_sources']]
  if row.get('blueprint'):
   (run/'blueprint.json').write_text(json.dumps(row['blueprint'],ensure_ascii=False,indent=2))
  if row.get('result'):
   (run/'result.json').write_text(json.dumps(row['result'],ensure_ascii=False,indent=2))
   meta=row['result'].get('metadata',{});s=meta.get('summary',{})
   summary['generation_summary']={k:v for k,v in s.items() if k in ('success','source','requested','template_count','completed','failed')}
   summary['usage_summary']=next((e['metadata'].get('usage_summary') for e in row['events'] if e['type']=='done'),None)
  summary['knowledge_ingestion_blocked_calls']=len(blocked)
  summary['embedding_calls']=sum('/embeddings' in c['path'] or c['port']==8189 for c in network)
  summary['network']=network
  (OUT/'isolated.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
  print('FINAL',summary['final'],flush=True)
finally:
 process.terminate()
 try:process.wait(timeout=15)
 except subprocess.TimeoutExpired:process.kill();process.wait()
 log.close()
 if tasks:tasks.close()
 engine.dispose()
