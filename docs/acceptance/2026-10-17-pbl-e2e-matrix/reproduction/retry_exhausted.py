import json,time,asyncio
from pathlib import Path
import httpx
root=Path('/tmp/pbl-matrix-20261017/matrix_shop_b');out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-e2e-matrix')
async def main():
 auth=json.loads((root/'auth.json').read_text());created=json.loads((root/'created.json').read_text());h={'Authorization':'Bearer '+auth['token']};base='http://127.0.0.1:8027'
 before=len(list(root.glob('input-*.json')));start=time.time()
 async with httpx.AsyncClient(timeout=120) as client:
  response=await client.post(base+'/api/jobs/'+created['jobId']+'/retry',headers=h);response.raise_for_status();retried=response.json()
  for _ in range(180):
   detail=(await client.get(base+'/api/pbl/'+created['exerciseId'],headers=h)).json()
   if detail['job']['edu_job_id']==retried['edu_job_id'] and detail['job']['status'] in ('succeeded','failed','canceled'):break
   await asyncio.sleep(.5)
  after=len(list(root.glob('input-*.json')))
  result={'originalJob':created['jobId'],'retryJob':retried['edu_job_id'],'httpStatus':response.status_code,'finalStatus':detail['job']['status'],'errorCode':detail['job'].get('error_code'),'errorMessage':detail['job'].get('error_message'),'modelCallsBefore':before,'modelCallsAfter':after,'newModelCalls':after-before,'artifactPublished':bool(detail.get('artifact')),'seconds':round(time.time()-start,2)}
  (out/'exhausted-retry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False),flush=True)
asyncio.run(main())
