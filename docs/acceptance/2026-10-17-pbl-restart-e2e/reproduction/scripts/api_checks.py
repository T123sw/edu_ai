import asyncio,json,uuid,time
from pathlib import Path
import httpx
root=Path('/tmp/pbl-restart-20261017');out=Path('/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-17-pbl-restart-e2e');API='http://127.0.0.1:8027'
def read(p):return json.loads(p.read_text())
async def main():
 d=root/'matrix_score';a=read(d/'detail.json')['artifact'];auth=read(d/'auth.json');files=read(d/'private.json')['candidate_private']['completed'][-1]['candidate']['referenceFiles'];path=API+'/api/pbl/'+a['exerciseId'];result={}
 h={'Authorization':'Bearer '+auth['token']}
 async with httpx.AsyncClient(timeout=120) as client:
  other=(await client.post(API+'/api/auth/login',json={'username':'matrix_outsider','password':'matrix-isolated-only'})).json();oh={'Authorization':'Bearer '+other['token']}
  result['anonymousDetailStatus']=(await client.get(path)).status_code
  result['crossOwner']={suffix:(await client.get(path+suffix,headers=oh)).status_code for suffix in ('','/workspace','/runs')}
  payload={'artifactVersion':a['artifactVersion'],'taskId':a['tasks'][-1]['id'],'runId':str(uuid.uuid4()),'files':files}
  result['crossOwnerCheckStatus']=(await client.post(path+'/check',headers=oh,json=payload)).status_code
  report=await client.post(path+'/check',headers=h,json=payload);report.raise_for_status();assert report.json()['status']=='passed'
  replay=await client.post(path+'/check',headers=h,json=payload);assert replay.json()==report.json();result['runIdReplayReturnsSameReport']=True
  conflict=await client.post(path+'/check',headers=h,json={**payload,'files':{**files,'/src/App.jsx':files['/src/App.jsx']+'\n// conflicting request'}});result['runIdConflictStatus']=conflict.status_code
  escaped=await client.post(path+'/check',headers=h,json={**payload,'runId':str(uuid.uuid4()),'files':{**files,'/etc/test.txt':'blocked'}});result['unallowedFileStatus']=escaped.status_code
  workspace=(await client.get(path+'/workspace',headers=h)).json();patch={k:workspace[k] for k in ('artifactVersion','files','activeTaskId','customInputText')};patch['expectedRevision']=workspace['revision']
  writes=await asyncio.gather(*(client.put(path+'/workspace',headers=h,json={**patch,'mutationId':str(uuid.uuid4()),'customInputText':f'concurrent-{n}'}) for n in (1,2)))
  result['concurrentSaveStatuses']=sorted(r.status_code for r in writes);assert result['concurrentSaveStatuses']==[200,409]
  current=(await client.get(path+'/workspace',headers=h)).json();restore=await client.put(path+'/workspace',headers=h,json={**patch,'expectedRevision':current['revision'],'mutationId':str(uuid.uuid4())});restore.raise_for_status()
  assert result['anonymousDetailStatus']==401 and all(x==404 for x in result['crossOwner'].values()) and result['crossOwnerCheckStatus']==404
  assert result['runIdConflictStatus']==409 and result['unallowedFileStatus']==422
  result['passed']=True
  (out/'api-contracts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('API',result,flush=True)

asyncio.run(main())
