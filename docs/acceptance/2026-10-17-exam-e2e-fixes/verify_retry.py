"""Retry a failed isolated full-paper run through the real task-center API."""
import os,json,time,threading,socket,secrets,subprocess
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
previous=json.loads((OUT/'isolated.json').read_text());run=Path(previous['run_directory']);owner=previous['owner'];old=previous['generation_id']
from core.config import Config
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
from app.exam_generation.snapshots import SnapshotCodec
codec=SnapshotCodec()
for key in list(os.environ):
 if key.endswith('_PERSISTENCE_MODE'):os.environ[key]='json'
os.environ.update(DATABASE_URL='sqlite:///'+str(run/'state.db'),JOB_PERSISTENCE_MODE='json',APP_STATE_PERSISTENCE_MODE='json',MATERIAL_PERSISTENCE_MODE='json',COURSE_STORAGE_ROOT=str(run/'courses'),PYTHON_DOTENV_DISABLED='1')
for key,name in {'STORAGE_ROOT':'app','RUNTIME_CONFIG_ROOT':'config','VECTOR_DB_PATH':'vectors','DOCUMENT_INDEX_PATH':'documents.json','DOCUMENTS_ROOT':'documents','VIDEOS_ROOT':'videos','VIDEO_CHUNKS_ROOT':'chunks','TEMP_DIR':'temp'}.items():
 value=run/name;os.environ[key]=str(value);setattr(Config,key,value)
from app.exam_generation.repository import GenerationRepository,identifier,GenerationNotFound
from app.exam_generation.service import ExamGenerationHandler
from app.chat.tasks.task_store import TaskStore,get_task_store
from app.services.durable_task_executor import DurableTaskExecutor
from app.services.durable_task_handlers import DurableTaskHandlerRegistry
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import get_job
from app.api import jobs
from app.auth import get_current_user
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
token=secrets.token_urlsafe(40);os.environ.update(EDU_DEEPTUTOR_URL=f'http://127.0.0.1:{port}',EDU_DEEPTUTOR_TOKEN=token)
env={**os.environ,'DEEPTUTOR_HOME':str(run/'deeptutor')};env.pop('PYTHONPATH',None)
service=ROOT/'services/deeptutor';log=(run/'retry-service.log').open('w');process=subprocess.Popen([str(service/'.venv/bin/python'),'-m','uvicorn','edu_deeptutor.api:create_app','--factory','--host','127.0.0.1','--port',str(port)],cwd=service,env=env,stdout=log,stderr=subprocess.STDOUT)
summary={'source_generation_id':old,'owner':owner,'run_directory':str(run),'attempts':[]}
tasks=TaskStore(str(run/'tasks.db'));registry=DurableTaskHandlerRegistry();registry.register('exam_generate',1,ExamGenerationHandler(codec=codec));executor=DurableTaskExecutor(task_store=tasks,handler_registry=registry,completion_service=JobCompletionService(task_store=tasks),lease_seconds=60,heartbeat_interval=10)
try:
 for _ in range(120):
  try:
   if httpx.get(f'http://127.0.0.1:{port}/health',trust_env=False,timeout=1).status_code==200:break
  except httpx.HTTPError:pass
  time.sleep(.25)
 jobs.get_task_store=lambda:tasks
 app=FastAPI();app.include_router(jobs.router);app.dependency_overrides[get_current_user]=lambda:{'username':owner};app.dependency_overrides[get_task_store]=lambda:tasks
 with TestClient(app) as client:
  prior_job=old
  for attempt in range(2):
   response=client.post('/api/jobs/'+prior_job+'/retry');response.raise_for_status();job_id=response.json()['edu_job_id'];gid=identifier(owner,str(uuid5(NAMESPACE_URL,job_id)));started=time.monotonic()
   worker=threading.Thread(target=executor.run_once,daemon=True);worker.start()
   while worker.is_alive():worker.join(timeout=2)
   job=get_job(job_id);row=GenerationRepository().get(owner,gid);result=(row.get('result') or {}).get('metadata',{}).get('summary',{})
   usage=next((e['metadata'].get('usage_summary') for e in row['events'] if e['type']=='done'),None)
   entry={'generation_id':gid,'job_id':job_id,'seconds':round(time.monotonic()-started,2),'status':job.status.value,'completed':result.get('completed'),'failed':result.get('failed'),'usage_summary':usage}
   summary['attempts'].append(entry);(OUT/'retry.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));(run/f'retry-{attempt+1}-record.json').write_text(json.dumps({k:v for k,v in row.items() if k!='encrypted_snapshot'},ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in entry.items() if k!='usage_summary'}),flush=True)
   if job.status.value=='succeeded':break
   prior_job=job_id
finally:
 process.terminate()
 try:process.wait(timeout=15)
 except subprocess.TimeoutExpired:process.kill();process.wait()
 log.close();tasks.close()
