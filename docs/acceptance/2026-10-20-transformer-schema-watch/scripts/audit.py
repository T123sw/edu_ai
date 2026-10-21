"""Read-only action receipts and deterministic submission audit."""
import json,os,sys
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
OUT=Path(__file__).resolve().parents[1]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from sqlalchemy import create_engine,text
from app.chat.harness.preparation_write_contract import PreparationWriteContract
from app.course_preparation.harness_generation import ContentTools
engine=create_engine(os.environ['DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on -c statement_timeout=10000'})
with engine.connect() as c:
 rows=[dict(r) for r in c.execute(text('select action_id,kind,status,created_at,payload,consumed,receipt from preparation_actions where preparation_id=:p order by created_at'),{'p':'prep_4406eb8b05ec47bdb9b1609e35e31ab5'}).mappings()]
(OUT/'actions.json').write_text(json.dumps(rows,ensure_ascii=False,default=str,indent=2))
specs=[json.loads(p.read_text()) for p in OUT.glob('artifact_*/spec.json')]
issues=[];recoveries=[]
for r in rows:
 m=(r['receipt'] or {}).get('model_response') or {}
 if m.get('protocol_recovery_attempt',0):recoveries.append({'at':str(r['created_at']),'phase':m.get('phase'),'attempt':m['protocol_recovery_attempt'],'action_id':r['action_id']})
 if m.get('phase')!='resource_write':continue
 for c in m.get('response',{}).get('choices',[]):
  for t in c['message'].get('tool_calls') or []:
   try:v=json.loads(t['function']['arguments'])
   except (ValueError,KeyError):continue
   if not isinstance(v,dict):continue
   for spec in specs:
    context=spec.get('teaching_context',{});bindings=v.get('objective_bindings',[])
    if not bindings or bindings[0].get('objective_id') not in context.get('objective_ids',[]):continue
    kind='quiz' if isinstance(v.get('content'),dict) else 'report'
    if spec.get('resource_type')!=kind:continue
    contract=PreparationWriteContract(kind,context,'observed')
    tool=ContentTools(lambda:None,structured=True,response_schema=contract.schema,response_validator=contract.validate_submission)
    try:tool.validate_arguments('submit_resource_json',v)
    except Exception as e:
     issue={'at':str(r['created_at']),'node':spec['node_id'],'phase':'resource_write','protocol_attempt':m.get('protocol_recovery_attempt'),'error':str(e),'action_id':r['action_id']}
     if issue not in issues:issues.append(issue)
(OUT/'write-contract-issues.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2))
summary={'at':datetime.now(timezone.utc).isoformat(),'action_counts':dict(Counter(r['status'] for r in rows)),'protocol_recoveries':recoveries,'write_contract_issues':issues,'failed_actions':[r for r in rows if r['status']=='failed']}
(OUT/'action-audit.json').write_text(json.dumps(summary,ensure_ascii=False,default=str,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='failed_actions'},ensure_ascii=False))
