"""Replay real events in a temporary PostgreSQL schema; never mutate business rows."""
import os,json,time,asyncio,copy
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
from core.config import Config
from sqlalchemy import create_engine,select,text
from app.database.models import AppStateRecord
from app.database.session import database_session
from app.exam_generation.repository import GenerationRepository,NAMESPACE
from app.exam_generation.service import ExamGenerationHandler
from app.services.durable_task_handlers import DurableExecutionContext
original=json.loads((ROOT/'.runtime/exam-real-paper-e2e/examgen_e5e47a9ab726c9fac99cc0284fd98fee-record.json').read_text())
events=[json.loads(x) for x in (ROOT/'.runtime/exam-real-paper-e2e/full-events.ndjson').read_text().splitlines()]
base=create_engine(os.environ['DATABASE_URL']);schema='exam_bench_'+uuid4().hex[:12]
with base.begin() as c:c.execute(text('CREATE SCHEMA '+schema))
engine=base.execution_options(schema_translate_map={None:schema})
summary={'schema_isolated':True,'event_count':len(events),'source_payload_bytes':len(json.dumps(original['parsed_sources']))}
def old_batch(repo,gid,batch):
 with database_session(engine=engine) as session:
  row=repo._row(session,'benchmark',gid,lock=True);value=copy.deepcopy(row.payload)
  for event in batch:
   if event['seq']<=value['last_seq']:continue
   session.add(AppStateRecord(namespace=NAMESPACE+'_events',record_key=f"{gid}:{event['seq']:020d}",owner_user_id='benchmark',payload=copy.deepcopy(event)))
   value['last_seq']=event['seq']
   blueprint=event.get('metadata',{}).get('exam_blueprint')
   if blueprint is not None:value['blueprint']=blueprint
   if event['type']=='result':value['result']=event
  row.payload=value
try:
 AppStateRecord.__table__.create(engine)
 repo=GenerationRepository(engine)
 def create():
  request={**original['request'],'request_id':str(uuid4())}
  row=repo.create('benchmark',request,sources=original['sources'],encrypted_snapshot='isolated')
  repo.claim('benchmark',row['id'],1)
  repo.update('benchmark',row['id'],1,{'parsed_sources':original['parsed_sources'],'turn_id':'replay','session_id':'replay'})
  return row
 for label,size in [('previous_repository',100),('new_repository',500)]:
  row=create();start=time.monotonic()
  for offset in range(0,1000,size):
   batch=events[offset:offset+size]
   if label.startswith('previous'):old_batch(repo,row['id'],batch)
   else:repo.events_batch('benchmark',row['id'],1,batch)
  summary[label+'_1000_seconds']=round(time.monotonic()-start,3)
  print(label,summary[label+'_1000_seconds'],flush=True)
 row=create();reads={'lease':0,'cancel':0}
 def query(kind):
  reads[kind]+=1
  with engine.connect() as c:
   return c.scalar(select(AppStateRecord.payload['attempt'].as_integer()).where(AppStateRecord.namespace==NAMESPACE,AppStateRecord.record_key==row['id']))
 class Client:
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def status(self,**kwargs):return {'status':'completed'}
  async def internal_events(self,after_seq,**kwargs):
   for event in events:
    if event['seq']>after_seq:yield event
 class Codec:
  def read(self,*args):return {}
 ctx=DurableExecutionContext(task_id=row['id'],owner_user_id='benchmark',course_id=None,config_snapshot_id=None,progress=lambda *a:None,is_cancel_requested=lambda:query('cancel')!=1,attempt_count=1,is_lease_valid=lambda:query('lease')==1)
 started=time.monotonic();result=asyncio.run(ExamGenerationHandler(repo,codec=Codec(),client_factory=Client).run({'generation_id':row['id']},ctx));summary['full_handler_seconds']=round(time.monotonic()-started,3)
 stored=repo.get('benchmark',row['id']);assert [x['seq'] for x in stored['events']]==[x['seq'] for x in events]
 assert stored['last_seq']==events[-1]['seq'] and result['saved']
 summary.update(reads=reads,all_events_preserved=True,questions=stored['result']['metadata']['summary']['completed'],last_seq=stored['last_seq'])
 (OUT/'event-benchmark.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)
finally:
 with base.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
 base.dispose()
