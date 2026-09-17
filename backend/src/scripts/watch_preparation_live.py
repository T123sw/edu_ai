"""Retain HTTP status history and intermediate products of an existing live task."""
import argparse,json,time
from pathlib import Path
import httpx
p=argparse.ArgumentParser();p.add_argument('--id',required=True);p.add_argument('--output',required=True);p.add_argument('--credentials');a=p.parse_args()
root=Path(__file__).resolve().parents[3]
c=json.loads(Path(a.credentials).read_text() if a.credentials else (root/'artifacts/full-application/credentials.json').read_text())
out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
client=httpx.Client(base_url='http://127.0.0.1:8027',headers={'Authorization':'Bearer '+c['token']},timeout=60)
last=None;path='/api/course-preparations/'+a.id
for i in range(1200):
 r=client.get(path);r.raise_for_status();state=r.json()
 if state!=last:
  with (out/'preparation-status.jsonl').open('a') as f:f.write(json.dumps({'observed_at':time.time(),**state},ensure_ascii=False)+'\n')
  if last is None or state['stage']!=last['stage']:
   detail=client.get(path+'/intermediates');detail.raise_for_status();(out/(str(i)+'-'+state['stage']+'.json')).write_text(json.dumps(detail.json(),ensure_ascii=False,indent=2))
   print(state['stage'],state['status'],flush=True)
  last=state
 if state['status'] in ('succeeded','failed','canceled'):break
 time.sleep(3)
(out/'preparation-final.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
if state['status']=='succeeded':
 r=client.get('/api/self-learning/courses/'+state['result_ref']['course_id']);r.raise_for_status();(out/'learning-room.json').write_text(json.dumps(r.json(),ensure_ascii=False,indent=2))
print(state['status'],state.get('error_code'))
raise SystemExit(0 if state['status']=='succeeded' else 1)
