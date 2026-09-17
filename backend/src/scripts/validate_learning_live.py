"""Authenticated real-model diagnostic against the isolated full application."""
import argparse,json,time
from pathlib import Path
from uuid import uuid4
import httpx
p=argparse.ArgumentParser();p.add_argument('--question',required=True);p.add_argument('--name',required=True);p.add_argument('--expect-preparation',action='store_true');p.add_argument('--current-version',action='store_true')
a=p.parse_args();root=Path(__file__).resolve().parents[3]/'artifacts'/'full-application'
c=json.loads((root/'credentials.json').read_text());state=json.loads((root/'state.json').read_text())
room=next(r for r in state['rooms'] if r['id']==c['course_id']);chapter=room['chapters'][0]
resource=next(r['remote'] for r in chapter['resources'] if r['remote']['materialType']=='report')
out=root/a.name;out.mkdir(exist_ok=False)
client=httpx.Client(base_url='http://127.0.0.1:8027',headers={'Authorization':'Bearer '+c['token']},timeout=120)
if a.current_version:
 r=client.get('/api/self-learning/courses/'+c['course_id']);r.raise_for_status();room=r.json();chapter=room['chapters'][0]
 resource=next(r['remote'] for r in chapter['resources'] if r['remote']['materialType']=='report')
def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
request={'request_id':str(uuid4()),'question':a.question,'reading_context':{'resource_ref':{'course_id':room['id'],'material_type':'report','material_id':resource['materialId'],'version':resource['version']}}}
save('request.json',request)
r=client.post('/api/self-learning/courses/'+room['id']+'/topics/'+chapter['id']+'/agent-turns',json=request);r.raise_for_status();turn=r.json();save('receipt.json',turn)
for i in range(150):
 r=client.get('/api/self-learning/agent-turns/'+turn['turn_id']);r.raise_for_status();turn=r.json();save('turn.json',turn)
 if turn['status'] in ('succeeded','failed','canceled'):break
 time.sleep(2)
print(json.dumps(turn,ensure_ascii=False),flush=True)
if a.expect_preparation:
 assert turn.get('preparation_receipts'), 'Save request did not return a durable preparation receipt'
raise SystemExit(0 if turn['status']=='succeeded' else 1)
