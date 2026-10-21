"""Inject the recorded defect, then request a real correction; no task writes."""
from pathlib import Path
import json,sys,time,hashlib
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
import httpx
from app.course_preparation.research_dependencies import agent_factory
from app.course_preparation.research_contracts import ResearchState
from app.course_preparation.node_research import review_node

OUT=ROOT/'docs/acceptance/2026-10-19-node-review-schema-recovery'
SOURCE=ROOT/'docs/acceptance/2026-10-19-transformer-adaptive-watch'
checkpoint=json.loads((SOURCE/'checkpoint.json').read_text())
recorded=json.loads((SOURCE/'actions.json').read_text())[-1]['receipt']['model_response']['response']
state=ResearchState.model_validate(checkpoint['research_state'])
node=next(n for n in state.path.nodes if n.node_key=='n2-self-attention')
ledger=[];calls=[]
class Meter:
    def start(self,**kwargs):
        row={'reserved':kwargs};ledger.append(row);return row
    def finish(self,action,**kwargs):action.update(kwargs)

def complete(request):
    payload=json.loads(request.content)
    call={'index':len(calls),'kind':'recorded_response_replay' if not calls else 'real_provider_request'}
    calls.append(call)
    if len(calls)==1:return httpx.Response(200,json=recorded)
    assert 'sufficient_again' in payload['messages'][-1]['content']
    call['feedback']=payload['messages'][-1]['content']
    start=time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(50,connect=10)) as client:
        response=client.post(str(request.url),headers=dict(request.headers),content=request.content)
    call['seconds']=time.monotonic()-start
    call['http_status']=response.status_code
    return response

model=agent_factory('teacher',checkpoint['config_snapshot']).model
model.retry_only=True
model.meter=Meter()
model.client_factory=lambda **kw:httpx.Client(transport=httpx.MockTransport(complete),**kw)
original=state.model_dump(mode='json');start=time.monotonic()
try:
    decision=review_node(model,state,node,timeout=60,preferences=checkpoint.get('memory_view'))
    result={'status':'recovered','decision':decision.model_dump(mode='json')}
except Exception as exc:
    result={'status':'failed','error':type(exc).__name__,'code':getattr(exc,'code',None),'message':str(exc)}
result.update(seconds=time.monotonic()-start,model=model.gateway.candidates[0]['model_name'],calls=calls,
              input_state_unchanged=original==state.model_dump(mode='json'),original_task_mutated=False,
              sources_reread=False,ledger=ledger)
(OUT/'live-replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='ledger'},ensure_ascii=False))
assert result['status']=='recovered',result.get('message')
assert result['input_state_unchanged']
assert len(calls)>=2 and ledger[1]['response_data']['protocol_recovery_attempt']==1
