import asyncio,json,time,uuid
from pathlib import Path
import httpx
from sqlalchemy import create_engine,text
API='http://127.0.0.1:8027';root=Path('/tmp/pbl-fixes-final-20261017');out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-fixes')
engine=create_engine('postgresql+psycopg://zxqs_ep@127.0.0.1:55441/pbl_acceptance_20261017_final')
def save(name,data):(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def checkpoint(identifier):
 with engine.connect() as c:return c.execute(text('select checkpoint,artifact_public,current_job_id from pbl_exercises where id=:id'),{'id':identifier}).mappings().one()
async def main():
 result={'productionDataModified':False};start=time.time()
 async with httpx.AsyncClient(timeout=120) as client:
  auth=(await client.post(API+'/api/auth/login',json={'username':'matrix_recovery','password':'matrix-isolated-only'})).json();h={'Authorization':'Bearer '+auth['token']}
  created=(await client.post(API+'/api/pbl',headers=h,json={'request_id':str(uuid.uuid4()),'topic':'做一个仅在本页运行的姓名欢迎卡片，只需一个交互步骤。姓名输入框和“打招呼”按钮，输入姓名后点击显示“你好，”加姓名，空白姓名提示“请输入姓名”。无其他功能。'})).json()
  identifier=created['exerciseId'];path=API+'/api/pbl/'+identifier;result['exerciseId']=identifier
  try:
   for _ in range(2400):
    detail=(await client.get(path,headers=h)).json();job=detail['job'];
    if job['step']=='pbl_build_checks':break
    if job['status'] in ('succeeded','failed','canceled'):raise AssertionError('did not reach cancellation window: '+job['status'])
    await asyncio.sleep(.25)
   before=checkpoint(identifier)['checkpoint'];result['pendingCodeBeforeCancel']=bool(before.get('pending',{}).get('implementation'))
   assert result['pendingCodeBeforeCancel']
   response=await client.post(API+'/api/jobs/'+created['jobId']+'/cancel',headers=h);response.raise_for_status();result['cancelResponse']=response.json()['status']
   for _ in range(100):
    detail=(await client.get(path,headers=h)).json()
    if detail['job']['status']=='canceled':break
    await asyncio.sleep(.2)
   assert detail['job']['status']=='canceled' and not detail['artifact'];result['canceledWithoutPublication']=True
   response=await client.post(API+'/api/jobs/'+created['jobId']+'/retry',headers=h);response.raise_for_status();retry=response.json();result['retryJobId']=retry['edu_job_id'];assert result['retryJobId']!=created['jobId']
   for _ in range(300):
    detail=(await client.get(path,headers=h)).json()
    if detail.get('artifact') or (detail['job']['edu_job_id']==result['retryJobId'] and detail['job']['status'] in ('failed','canceled')):break
    await asyncio.sleep(1)
   assert detail.get('artifact'),detail['job']
   inputs=[json.loads(p.read_text()) for p in sorted((root/'matrix_recovery').glob('input-*.json'))]
   result['modelPhases']=[x['phase'] for x in inputs]
   assert result['modelPhases'].count('build_step')==1 and result['modelPhases'].count('plan')==1
   accepted=[x['data'] for x in inputs if x['phase']=='build_checks']
   assert len(accepted)==2 and accepted[0]['referenceFiles']==accepted[1]['referenceFiles']
   result.update(passed=True,sameExerciseRetried=True,savedCodeReused=True,stepCount=len(detail['artifact']['tasks']))
  except Exception as exc:result.update(passed=False,error=str(exc),errorType=type(exc).__name__)
  result['seconds']=round(time.time()-start,2);save('real-cancel-retry.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
asyncio.run(main())
