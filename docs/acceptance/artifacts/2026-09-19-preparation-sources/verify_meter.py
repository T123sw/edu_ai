"""Opt-in real provider timings in a new isolated SQLite database. Synthetic owner authorization only."""
from pathlib import Path
import json, hashlib
import dotenv
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--env-file',required=True)
parser.add_argument('--output-dir',required=True)
args=parser.parse_args()
output=Path(args.output_dir).resolve()
output.mkdir(parents=True,exist_ok=False)
settings=dotenv.dotenv_values(args.env_file);dotenv.load_dotenv=lambda *a,**kw:False
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.database import Base
from app.database.models import User,PreparationAction
from app.course_preparation.lifecycle_repository import LifecycleRepository
from app.course_preparation.schemas import PreparationRequest
from app.course_preparation.research_sources import ResearchSources
from app.course_preparation.research_factory import MeteredSources
from uuid import uuid4
engine=create_engine('sqlite:///'+str(output/'meter.sqlite'))
names=('users','course_research_runs','course_preparations','course_preparation_attempts','course_preparation_events','preparation_budgets','preparation_executions','preparation_actions')
Base.metadata.create_all(engine,tables=[Base.metadata.tables[n] for n in names])
with Session(engine) as session,session.begin():session.add(User(user_id='meter-test',username='meter-test',password_hash='test-only',role='student'))
class Auth:
 def authorize(self,*a):pass
repo=LifecycleRepository(engine,authorizer=Auth())
task=repo.submit('meter-test',PreparationRequest(request_id=uuid4(),operation='create_course',goal='Verify source tool timing'))
context=repo.claim('test',preparation_id=task['preparation_id'])
source=ResearchSources(tavily_key=settings['TAVILY_API_KEY'],bocha_key=settings.get('BOCHA_API_KEY',''),tavily_base=settings.get('TAVILY_BASE_URL') or 'https://api.tavily.com')
source.attempt=MeteredSources(repo,context,source)._call
hits=source.search('DeepSeek official API tool calls Python',limit=2,timeout=25)
body=source.read_body('https://api-docs.deepseek.com/guides/tool_calls',timeout=25)
with Session(engine) as session:
 receipts=[{'kind':a.kind,'provider':a.payload.get('provider'),'receipt':a.receipt,'consumed':a.consumed} for a in session.scalars(select(PreparationAction).where(PreparationAction.preparation_id==context.preparation_id))]
result={'scope':'real Tavily search/extract with isolated SQLite action ledger; authentication stub for synthetic owner only','search_hits':len(hits),'body_characters':len(body['content']),'body_sha256':hashlib.sha256(body['content'].encode()).hexdigest(),'receipts':receipts}
(output/'meter-results.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
