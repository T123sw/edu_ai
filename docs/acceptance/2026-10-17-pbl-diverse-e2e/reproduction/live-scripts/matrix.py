import asyncio,json,time,uuid,sys,os
from pathlib import Path
import httpx
from sqlalchemy import create_engine,text
engine=create_engine('postgresql+psycopg://zxqs_ep@127.0.0.1:55441/pbl_acceptance_20261017_diverse')
root=Path('/tmp/pbl-diverse-20261017')
out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-diverse-e2e')
API='http://127.0.0.1:8027'
specs=json.loads((root/'cases.json').read_text())
cases={n:s['topic'] for n,s in specs.items()}

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

async def login(client,name):
 r=await client.post(API+'/api/auth/login',json={'username':'matrix_'+name,'password':'matrix-isolated-only'});r.raise_for_status();return r.json()

async def run(name,topic):
 case=root/('matrix_'+name);case.mkdir(exist_ok=True)
 start=time.time();events=[]
 async with httpx.AsyncClient(timeout=120) as client:
  auth=await login(client,name);save(case/'auth.json',auth)
  headers={'Authorization':'Bearer '+auth['token']}
  payload={'topic':topic,'request_id':str(uuid.uuid4())}
  response=await client.post(API+'/api/pbl',json=payload,headers=headers);response.raise_for_status();created=response.json();save(case/'created.json',created)
  again=await client.post(API+'/api/pbl',json=payload,headers=headers);assert again.json()['exerciseId']==created['exerciseId']
  identifier=created['exerciseId'];path=API+'/api/pbl/'+identifier
  print(name,'CREATED',identifier,flush=True)
  final=None
  for _ in range(1200):
   response=await client.get(path,headers=headers);response.raise_for_status();detail=response.json();job=detail['job'] or {}
   state=(job.get('status'),job.get('step'),job.get('message'))
   if not events or events[-1]['state']!=list(state):
    events.append({'seconds':round(time.time()-start,2),'state':list(state)});print(name,*state,flush=True)
   if detail.get('artifact') or job.get('status') in ('failed','canceled'):
    final=detail;break
   await asyncio.sleep(2)
  assert final is not None,'generation deadline'
  save(case/'detail.json',final)
  with engine.connect() as connection:
   row=connection.execute(text('select candidate_private, checkpoint from pbl_exercises where id=:id'),{'id':identifier}).mappings().one()
   save(case/'private.json',dict(row))
  result={'case':name,'topic':topic,'exerciseId':identifier,'generationPassed':bool(final.get('artifact')),'job':final['job'],'events':events,'seconds':round(time.time()-start,2),'idempotentCreate':True}
  save(out/(name+'-generation.json'),result)
  if final.get('artifact'):
   artifact=final['artifact'];result.update(stepCount=len(artifact['tasks']),checkCount=len(artifact['checks']))
   save(out/(name+'-artifact.json'),artifact)
  save(out/(name+'-generation.json'),result)
  return result

async def main():
 results=await asyncio.gather(*(run(n,t) for n,t in cases.items()),return_exceptions=True)
 save(out/'generation-summary.json',[{'error':str(x),'type':type(x).__name__} if isinstance(x,Exception) else {k:v for k,v in x.items() if k not in ('job','events')} for x in results])
 print('COMPLETE',[(x.get('case'),x.get('generationPassed')) if isinstance(x,dict) else str(x) for x in results],flush=True)

asyncio.run(main())
