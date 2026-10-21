"""Exercise the real generation/publish paths in disposable local storage."""
import os, asyncio, json, time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from isolated import configure
os.environ.pop('PBL_TEST_DATABASE_URL', None)
os.environ['PBL_ACCEPTANCE_STORAGE']='/tmp/pbl-model-statement-real/storage'
storage=configure(live_model=True)
from sqlalchemy import create_engine
from app.pbl.db_models import PblExercise,PblWorkspace,PblRun,PblTutorTurn
from app.pbl.repository import PblRepository
from app.pbl.service import generate_exercise
out=Path('/tmp/pbl-model-statement-real');out.mkdir(parents=True,exist_ok=True)
engine=create_engine('sqlite:///'+str(storage/'acceptance.db'),connect_args={'check_same_thread':False})
for model in (PblExercise,PblWorkspace,PblRun,PblTutorTurn):model.__table__.create(engine,checkfirst=True)
repo=PblRepository(engine=engine)
async def run(kind,topic):
    started=time.monotonic();owner='statement_'+kind
    row=repo.create_or_get(owner,str(uuid4()),topic)
    ctx=SimpleNamespace(task_id=row.current_job_id,owner_user_id=owner,is_cancel_requested=lambda:False,is_lease_valid=lambda:True,
        progress=lambda *args:print(kind,*args,flush=True))
    try:
        await asyncio.wait_for(generate_exercise({'exercise_id':row.id,'topic':topic,'runtime_config_snapshot':{}},ctx,repository=repo),timeout=300)
        artifact=repo.get_owned(owner,row.id).artifact_public
        assert artifact and artifact['validationSummary']['passed']
        (out/(kind+'.json')).write_text(json.dumps({'artifact':artifact},ensure_ascii=False,indent=2))
        result={'kind':kind,'passed':True,'steps':len(artifact['tasks']),'statementLengths':[len(t['instructionsMarkdown']) for t in artifact['tasks']], 'artifact':str(out/(kind+'.json'))}
    except Exception as exc:
        result={'kind':kind,'passed':False,'errorType':type(exc).__name__,'message':str(exc)[:200]}
    result['elapsedSeconds']=round(time.monotonic()-started,2)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result
async def main():
    results=await asyncio.gather(run('algorithm','快速排序练习：清楚描述输入输出和边界，提供一个普通乱序示例。'),run('project','做一个最小 React 按钮计数器，在一个步骤内完成：初始显示 0，点击增加按钮加 1，点击重置回到 0。不增加其他功能。题目清楚说明任务要求即可。'))
    (out/'verification.json').write_text(json.dumps({'productionModified':False,'model':'real configured default provider','storage':str(storage),'runtime':'real algorithm Worker and project browser checker','results':results},ensure_ascii=False,indent=2))
asyncio.run(main())
