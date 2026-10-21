"""Read-only production audit restricted to this run's dedicated test owner."""
import sys,os,json,sqlite3,hashlib,collections,time
from pathlib import Path
from sqlalchemy import create_engine,select,text,func
from core.config import Config
from app.database.models import AppStateRecord,KnowledgeLibrary,KnowledgeDocument
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/sys.argv[1]
browser=json.loads((OUT/'online-browser.json').read_text());tag=browser['tag']
auth=json.loads((ROOT/'.runtime/exam-real-paper-e2e/auth.json').read_text());owner=auth['username']
base=ROOT/'services/deeptutor/.runtime/data/users'/('edu_'+hashlib.sha256(owner.encode()).hexdigest())/'user'
journal=sqlite3.connect((base/'chat_history.db').as_uri()+'?mode=ro',uri=True);journal.row_factory=sqlite3.Row
ledger=sqlite3.connect((base/'usage.sqlite3').as_uri()+'?mode=ro',uri=True)
engine=create_engine(os.environ['DATABASE_URL']);report={'observed_at':time.time(),'tag':tag,'generations':[]};papers=[]
with engine.connect() as c:
 c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
 rows=c.execute(select(AppStateRecord.payload).where(AppStateRecord.namespace=='exam_generation_v1',AppStateRecord.owner_user_id==owner,AppStateRecord.payload['request']['requirement'].as_string().startswith(tag))).scalars().all()
 for row in rows:
  tid=row.get('turn_id');summary=(row.get('result') or {}).get('metadata',{}).get('summary',{})
  if not tid:continue
  events=c.execute(select(AppStateRecord.payload['type'].as_string()).where(AppStateRecord.namespace=='exam_generation_v1_events',AppStateRecord.owner_user_id==owner,AppStateRecord.record_key.like(row['id']+':%'))).scalars().all()
  turn=journal.execute('select id,status,failure_code,created_at,updated_at from turns where id=?',(tid,)).fetchone()
  upstream=journal.execute('select count(*) from turn_events where turn_id=?',(tid,)).fetchone()[0]
  usage=[json.loads(x[0]) for x in ledger.execute('select usage_json from llm_calls where turn_id=?',(tid,))]
  g={'generation_id':row['id'],'job_id':row.get('job_id'),'turn':dict(turn) if turn else None,'parsed':[{'parser':s['parser'],'characters':len(s['content']),'layout_blocks':len(s['content_list']),'images':len(s['images'])} for s in row.get('parsed_sources') or []],
   'blueprint_count':len((row.get('blueprint') or {}).get('questions',[])),'local_events':len(events),'upstream_events':upstream,'done_received':'done' in events,
   'summary':{k:v for k,v in summary.items() if k in ('success','requested','template_count','completed','failed')},
   'failed_questions':[{'ordinal':i+1,'issues':q.get('metadata',{}).get('issues',[])} for i,q in enumerate(summary.get('results',[])) if q.get('metadata',{}).get('review_passed') is False],
   'usage':{'recorded_calls':len(usage),'models':dict(collections.Counter(v['model'] for v in usage))}}
  report['generations'].append(g);papers.append((g,summary))
  target=ROOT/'.runtime/exam-multi-pdf-20261018'/(row['id']+'-production.json');target.write_text(json.dumps({k:v for k,v in row.items() if k!='encrypted_snapshot'},ensure_ascii=False,indent=2));target.chmod(0o600)
 report['owner_knowledge_libraries']=c.scalar(select(func.count()).select_from(KnowledgeLibrary).where(KnowledgeLibrary.owner_user_id==owner))
 report['owner_knowledge_documents']=c.scalar(select(func.count()).select_from(KnowledgeDocument).join(KnowledgeLibrary).where(KnowledgeLibrary.owner_user_id==owner));c.rollback()
engine.dispose()
papers.sort(key=lambda p:(p[0]['turn'] or {}).get('created_at',0));report['generations']=[g for g,s in papers]
if len(papers)>1:
 first={q['qa_pair']['question_id']:q['qa_pair'] for q in papers[0][1].get('results',[]) if q['metadata'].get('review_passed')}
 latest={q['qa_pair']['question_id']:q['qa_pair'] for q in papers[-1][1].get('results',[]) if q['metadata'].get('review_passed')}
 report['retry_preservation']={'first_accepted':len(first),'unchanged_in_latest':sum(latest.get(k)==v for k,v in first.items())}
baseline=ROOT/'.runtime/exam-multi-pdf-20261018'/(OUT.name+'-before-context-fix.json')
completed_papers=[p for p in papers if p[1].get('results')]
if baseline.exists() and completed_papers:
 def projection(q):
  return {k:q.get(k) for k in ('question_id','question','question_type','options','correct_answer','correct_answers','blank_answers','explanation')} | {'children':[projection(c) for c in q.get('children') or []]}
 before={q['question_id']:projection(q) for q in json.loads(baseline.read_text())}
 after={q['qa_pair']['question_id']:projection(q['qa_pair']) for q in completed_papers[-1][1]['results'] if q['metadata'].get('review_passed')}
 report['hotfix_preservation']={'compared_generation_id':completed_papers[-1][0]['generation_id'],'accepted_before':len(before),'unchanged_in_latest':sum(after.get(k)==v for k,v in before.items()),'missing_or_changed_ids':[k for k,v in before.items() if after.get(k)!=v]}
(OUT/'online-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'generations':[{k:v for k,v in g.items() if k not in ('failed_questions','usage')} for g in report['generations']],'no_knowledge_records':report['owner_knowledge_libraries']==report['owner_knowledge_documents']==0},ensure_ascii=False))
