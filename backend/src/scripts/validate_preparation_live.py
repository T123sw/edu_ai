"""Real HTTP preparation acceptance with immutable request and intermediate logs."""
import argparse,json,time,subprocess
from pathlib import Path
from uuid import uuid4
import httpx
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--goal',required=True);p.add_argument('--minutes',type=int,default=30);p.add_argument('--classroom',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[3];creds=json.loads((root/'artifacts/full-application/credentials.json').read_text());out=root/'artifacts'/'frozen-acceptance'/a.name;out.mkdir(parents=True,exist_ok=False)
def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
save('version.json',{'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'started_at':time.time(),'goal':a.goal})
client=httpx.Client(base_url='http://127.0.0.1:8027',headers={'Authorization':'Bearer '+creds['token']},timeout=60)
request={'request_id':str(uuid4()),'operation':'create_course','goal':a.goal,'overrides':{'total_minutes':a.minutes,'required_resource_types':['classroom'] if a.classroom else []},'source_policy':{'mode':'open'}};save('request.json',request)
r=client.post('/api/course-preparations',json=request);r.raise_for_status();receipt=r.json();save('receipt.json',receipt)
r=client.post('/api/course-preparations',json=request);r.raise_for_status();assert r.json()['preparation_id']==receipt['preparation_id']
path='/api/course-preparations/'+receipt['preparation_id'];previous=None
for tick in range(1200):
 r=client.get(path);r.raise_for_status();state=r.json()
 if state!=previous:
  with (out/'status.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),**state},ensure_ascii=False)+'\n')
  if previous is None or previous['stage']!=state['stage']:
   intermediate=client.get(path+'/intermediates');intermediate.raise_for_status();save(f'{tick:04d}-{state["stage"]}.json',intermediate.json());print(state['stage'],state['status'],flush=True)
  previous=state
 if state['status'] in ('succeeded','failed','canceled'):break
 time.sleep(3)
save('final.json',state);r=client.get(path+'/intermediates');r.raise_for_status();save('intermediates.json',r.json())
if state['status']=='succeeded':
 r=client.get('/api/self-learning/courses/'+state['result_ref']['course_id']);r.raise_for_status();save('learning-room.json',r.json())
 assert r.json()['manifestRef']['version']==state['result_ref']['manifest_version']
 assert all(v==0 for v in state['budget']['reserved'].values())
print(json.dumps(state,ensure_ascii=False),flush=True)
raise SystemExit(0 if state['status']=='succeeded' else 1)
