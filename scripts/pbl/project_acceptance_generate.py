"""Actual model generation on the dedicated acceptance DB only."""
import os, json, asyncio, uuid
from types import SimpleNamespace
from pathlib import Path
from isolated import configure
url=os.environ.get('PBL_TEST_DATABASE_URL','')
if 'pbl_acceptance' not in url: raise SystemExit('Use dedicated acceptance DB')
configure(live_model=True)
from sqlalchemy import create_engine
from app.database import Base
from app.pbl.repository import PblRepository
from app.pbl.service import generate_exercise
engine=create_engine(url);Base.metadata.create_all(engine)
repo=PblRepository(engine=engine)
row=repo.create_or_get('pbl_learner',str(uuid.uuid4()),'做一个四则运算计算器，通过四个步骤学习 React：构建按钮和显示区、数字和小数输入及清空、四则运算、除零错误与恢复。不需要键盘输入、运算符优先级或历史记录。')
path=Path('docs/acceptance/2026-10-14-pbl-project-integration')
(path/'exercise-id.txt').write_text(row.id)
ctx=SimpleNamespace(task_id=row.current_job_id,owner_user_id='pbl_learner',is_cancel_requested=lambda:False,is_lease_valid=lambda:True,progress=lambda *args:print(*args,flush=True))
asyncio.run(generate_exercise({'exercise_id':row.id,'topic':row.topic,'runtime_config_snapshot':{}},ctx,repository=repo))
row=repo.get_owned('pbl_learner',row.id)
(path/'real-model-artifact.json').write_text(json.dumps(row.artifact_public,ensure_ascii=False,indent=2))
# Private reference fixture stays in tmp; never in the public artifact or tracked evidence.
Path('/tmp/pbl-project-acceptance-private.json').write_text(json.dumps(row.candidate_private,ensure_ascii=False))
print('PUBLISHED',row.id,flush=True)
