"""Resume the existing failed preparation through its authorized service."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend/src'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from app.chat.tasks.task_store import get_task_store
from app.course_preparation.pipeline import build_pipeline
from sqlalchemy import text
PID='prep_531f57d76e274188b9bfd49fc9588dda';OUT=Path(__file__).resolve().parents[1]
app=build_pipeline(get_task_store())
before=app.service.get('teacher',PID)
with app.repository.engine.connect() as c:
 checkpoint=c.execute(text('SELECT checkpoint FROM preparation_executions WHERE preparation_id=:pid AND attempt_no=:attempt'),{'pid':PID,'attempt':before['attempt_no']}).scalar_one()
kept={k:checkpoint.get(k) for k in ('plan','research_summary','source_snapshots','node_research_checks')}
if before['attempt_no']==1 and before['status']=='failed' and before['error_code']=='STEP_FAILED':
 receipt=app.service.retry('teacher',PID)
 action='retried'
else:
 receipt=before;action='already_changed_no_duplicate_retry'
with app.repository.engine.connect() as c:
 after=c.execute(text('SELECT checkpoint FROM preparation_executions WHERE preparation_id=:pid AND attempt_no=:attempt'),{'pid':PID,'attempt':receipt['attempt_no']}).scalar_one()
checks={k:after.get(k)==v for k,v in kept.items()}
record={'action':action,'before':before,'receipt':receipt,'retained_checkpoints':checks}
(OUT/'resume.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'action':action,'attempt':receipt['attempt_no'],'stage':receipt['stage'],'status':receipt['status'],'retained_checkpoints':checks},ensure_ascii=False))
assert all(checks.values())
