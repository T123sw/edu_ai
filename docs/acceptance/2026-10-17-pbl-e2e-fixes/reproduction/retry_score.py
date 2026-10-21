import asyncio,json,time
from pathlib import Path
import httpx
from sqlalchemy import create_engine,text
root=Path('/tmp/pbl-fixes-final-20261017');out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-fixes');case=root/'matrix_score'
async def main():
 initial=json.loads((case/'detail.json').read_text());auth=json.loads((case/'auth.json').read_text());identifier=initial['exerciseId'];before=len(list(case.glob('input*.json')))
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8027',headers={'Authorization':'Bearer '+auth['token']},timeout=120) as client:
  response=await client.post('/api/jobs/'+initial['job']['edu_job_id']+'/retry');response.raise_for_status();job=response.json();print('RETRY',job['edu_job_id'],flush=True)
  for _ in range(600):
   detail=(await client.get('/api/pbl/'+identifier)).json()
   if detail['job']['edu_job_id']==job['edu_job_id'] and detail['job']['status'] in ('failed','succeeded','canceled'):break
   await asyncio.sleep(2)
  assert detail.get('artifact'),detail['job']
  (case/'detail.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2))
  engine=create_engine('postgresql+psycopg://zxqs_ep@127.0.0.1:55441/pbl_acceptance_20261017_final')
  with engine.connect() as c:
   row=c.execute(text('select candidate_private,checkpoint from pbl_exercises where id=:id'),{'id':identifier}).mappings().one();(case/'private.json').write_text(json.dumps(dict(row),ensure_ascii=False,indent=2))
   task=c.execute(text('select command,deadline_at,started_at from durable_tasks where task_id=:id'),{'id':job['edu_job_id']}).mappings().one()
  result={'exerciseId':identifier,'initialFailure':initial['job']['error_code'],'retryPassed':True,'modelCalls':len(list(case.glob('input*.json')))-before,'stepCount':len(detail['artifact']['tasks']),'checkCount':len(detail['artifact']['checks']),'queueWindow':task['command']['deadline_seconds'],'executionWindow':task['command']['execution_timeout_seconds'],'actualExecutionDeadlineSeconds':task['deadline_at']-task['started_at']}
  assert result['actualExecutionDeadlineSeconds']==1800
  (out/'deadline-retry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));(out/'score-artifact.json').write_text(json.dumps(detail['artifact'],ensure_ascii=False,indent=2));print(result,flush=True)
asyncio.run(main())
