import httpx,json,secrets,time,os
from pathlib import Path
from uuid import uuid4
root=Path('/home/zxqs_ep/Edu_AI'); work=root/'.runtime/exam-real-paper-e2e';out=root/'docs/acceptance/2026-10-17-exam-real-paper-e2e'
os.umask(0o077)
user='exam_e2e_'+uuid4().hex[:12]; password=secrets.token_urlsafe(24)
summary={'base':'http://127.0.0.1/backend','owner':user,'production_test_records':True,'timeline':[]}
with httpx.Client(base_url=summary['base'],timeout=90,trust_env=False) as client:
 r=client.post('/api/auth/register',json={'username':user,'password':password,'role':'student'}); r.raise_for_status()
 token=r.json()['token'];(work/'auth.json').write_text(json.dumps({'username':user,'password':password,'token':token}))
 client.headers['Authorization']='Bearer '+token
 r=client.post('/api/exam-generations/documents',files={'file':('USTC-2017-data-structures.pdf',(work/'source.pdf').read_bytes(),'application/pdf')});summary['upload_http']=r.status_code;r.raise_for_status();summary['upload']=r.json()
 payload={'request_id':str(uuid4()),'mode':'mimic','language':'zh','requirement':'依据整份原卷生成一套新的数据结构模拟试卷，保持原题顺序、题型和对应考点，保留子题结构，使用新的数据或情境，不照抄原题。','sources':[{'document_id':r.json()['document_id'],'role':'template'}]}
 r=client.post('/api/exam-generations',json=payload);summary['create_http']=r.status_code;r.raise_for_status();gid=r.json()['generation_id'];summary['generation_id']=gid
 started=time.monotonic()
 for i in range(120):
  r=client.get('/api/exam-generations/'+gid);r.raise_for_status();status=r.json()
  point={'seconds':round(time.monotonic()-started,2),**status}
  if not summary['timeline'] or status['message']!=summary['timeline'][-1]['message'] or status['status']!=summary['timeline'][-1]['status']:
   summary['timeline'].append(point);print(json.dumps(point,ensure_ascii=False),flush=True)
  (out/'online.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
  if status['status'] in ['succeeded','failed','canceled']:break
  time.sleep(2)
 print('FINAL',status['status'],flush=True)
