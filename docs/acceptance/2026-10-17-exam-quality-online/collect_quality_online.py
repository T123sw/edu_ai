"""Read-only audit of the dedicated test owner's two production generations."""
import os,json,collections,sqlite3,hashlib,time
from pathlib import Path
from core.config import Config
from sqlalchemy import create_engine,select,text,func
from app.database.models import AppStateRecord,KnowledgeLibrary,KnowledgeDocument
root=Path('/home/zxqs_ep/Edu_AI');out=root/'docs/acceptance/2026-10-17-exam-quality-online';private=root/'.runtime/exam-real-paper-e2e';auth=json.loads((private/'auth.json').read_text());owner=auth['username'];hashed=hashlib.sha256(owner.encode()).hexdigest()
base=root/'services/deeptutor/.runtime/data/users'/('edu_'+hashed)/'user'
journal=sqlite3.connect((base/'chat_history.db').as_uri()+'?mode=ro',uri=True);journal.row_factory=sqlite3.Row
ledger=sqlite3.connect((base/'usage.sqlite3').as_uri()+'?mode=ro',uri=True)
engine=create_engine(os.environ['DATABASE_URL']);result={'observed_at':time.time(),'generations':[]}
with engine.connect() as c:
 c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
 rows=c.execute(select(AppStateRecord.payload).where(AppStateRecord.namespace=='exam_generation_v1',AppStateRecord.owner_user_id==owner,AppStateRecord.payload['request']['requirement'].as_string().startswith('性能与质量上线复测'))).scalars().all()
 for row in rows:
  tid=row['turn_id'];events=c.execute(select(AppStateRecord.payload).where(AppStateRecord.namespace=='exam_generation_v1_events',AppStateRecord.owner_user_id==owner,AppStateRecord.record_key.like(row['id']+':%')).order_by(AppStateRecord.record_key)).scalars().all()
  cursor=c.scalar(select(AppStateRecord.payload['last_seq'].as_integer()).where(AppStateRecord.namespace=='exam_generation_v1_cursor',AppStateRecord.owner_user_id==owner,AppStateRecord.record_key==row['id']))
  turn=dict(journal.execute('select id,status,failure_code,created_at,updated_at from turns where id=?',(tid,)).fetchone())
  upstream_count=journal.execute('select count(*) from turn_events where turn_id=?',(tid,)).fetchone()[0]
  usage=[json.loads(x[0]) for x in ledger.execute('select usage_json from llm_calls where turn_id=?',(tid,))]
  summary=(row.get('result') or {}).get('metadata',{}).get('summary',{})
  g={'generation_id':row['id'],'job_id':row.get('job_id'),'turn':turn,'parsed':[{'parser':v['parser'],'characters':len(v['content']),'layout_blocks':len(v['content_list']),'images':len(v['images'])} for v in row.get('parsed_sources') or []], 'blueprint_count':len((row.get('blueprint') or {}).get('questions',[])),'local_event_count':len(events),'upstream_persisted_event_count':upstream_count,'separate_cursor':cursor,'emitted_questions':sum(e.get('metadata',{}).get('call_kind')=='quiz_question_emitted' for e in events),'errors':[e['content'] for e in events if e['type']=='error'],'done_received':any(e['type']=='done' for e in events),'summary':{k:v for k,v in summary.items() if k in ['success','requested','template_count','completed','failed']},'failed_questions':[{'ordinal':i+1,'issues':q.get('metadata',{}).get('issues',[])} for i,q in enumerate(summary.get('results',[])) if q.get('metadata',{}).get('review_passed') is False],'usage':{'recorded_calls':len(usage),'models':dict(collections.Counter(x['model'] for x in usage)),'status':dict(collections.Counter(x['status'] for x in usage)),'note':'Ledger interrupted may reflect early stream closure at protocol finish; it is not by itself a failed question.'}}
  result['generations'].append(g)
  p=private/(row['id']+'-record.json');p.write_text(json.dumps({k:v for k,v in row.items() if k!='encrypted_snapshot'},ensure_ascii=False,indent=2));p.chmod(0o600)
 result['owner_knowledge_libraries']=c.scalar(select(func.count()).select_from(KnowledgeLibrary).where(KnowledgeLibrary.owner_user_id==owner));result['owner_knowledge_documents']=c.scalar(select(func.count()).select_from(KnowledgeDocument).join(KnowledgeLibrary).where(KnowledgeLibrary.owner_user_id==owner))
 c.rollback()
engine.dispose()
checkpoints=root/'services/deeptutor/.runtime/edu_checkpoints'/hashed/'35a69225-c149-415f-ba89-84a77f87d05e';old=json.loads((out/'checkpoint-snapshot.json').read_text());files={json.loads(p.read_text())['question_id']:p for p in checkpoints.rglob('*.json')};first=[v for v in old if v['created_at']<1792253186]
result['checkpoints']={'first_passed':len(first),'current_passed':len(files),'first_unchanged':sum(v['id'] in files and hashlib.sha256(files[v['id']].read_bytes()).hexdigest()==v['sha256'] for v in first)}
original_emitted=[json.loads(x[0]) for x in journal.execute('SELECT metadata_json FROM turn_events WHERE turn_id=?',('turn_1792252817076_1899427d47',)) if json.loads(x[0]).get('call_kind')=='quiz_question_emitted']
original_pairs={m['qa_pair']['question_id']:m['qa_pair'] for m in original_emitted}
result['checkpoints']['first_emitted_content_unchanged']=sum(all(json.loads(files[v['id']].read_text()).get('topic' if k=='concentration' else k)==value for k,value in original_pairs[v['id']].items()) for v in first if v['id'] in files and v['id'] in original_pairs)
(out/'final-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({**result,'generations':[{k:v for k,v in g.items() if k not in ['failed_questions','usage']} for g in result['generations']]},ensure_ascii=False))
p=out/'live-monitor.json';monitor=json.loads(p.read_text())
for point in monitor['points']:
 if point['remote_seq']==0:
  point['lag_events']=None;point['note']='Upstream journal buffers live events; no reliable running lag measurement.'
p.write_text(json.dumps(monitor,ensure_ascii=False,indent=2)+'\n')
