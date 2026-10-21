"""Real-model PBL acceptance against a fresh SQLite repository and isolated config.

Usage: python scripts/pbl/native_acceptance_generate.py /tmp/pbl-native-run
No production users, jobs, workspaces or artifacts are accessed.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from uuid import uuid4
from isolated import configure

output=Path(sys.argv[1]).resolve()
if not str(output).startswith('/tmp/'): raise SystemExit('Use a fresh /tmp acceptance directory')
output.mkdir(parents=True,exist_ok=True)
os.environ['PBL_ACCEPTANCE_STORAGE']=str(output/'storage')
configure(live_model=True)
from sqlalchemy import create_engine
from app.pbl.db_models import PblExercise,PblWorkspace,PblRun,PblTutorTurn
from app.pbl.repository import PblRepository
from app.pbl import service,project_service

engine=create_engine('sqlite:///'+str(output/'acceptance.db'))
for model in (PblExercise,PblWorkspace,PblRun,PblTutorTurn): model.__table__.create(engine,checkfirst=True)
repository=PblRepository(engine=engine)
original=project_service.generate_project_phase
calls=[]
async def observed(owner,snapshot,phase,data):
    started=time.monotonic()
    try: return await original(owner,snapshot,phase,data)
    finally:
        calls.append({'phase':phase,'step':data.get('step',{}).get('id'),'seconds':round(time.monotonic()-started,2)})
        (output/'calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2))
project_service.generate_project_phase=observed
topics=[
    ('signup','做一个本地活动报名页面，分两步学习 React：第一步显示姓名输入框和提交按钮，姓名为空或仅空格时禁用提交；第二步提交非空姓名后显示报名成功和姓名，提供重新填写按钮清空输入与结果。不要后端、网络和其他功能。'),
    ('reading','做一个本地阅读清单，分两步：第一步输入书名并添加到列表，空白书名不添加且初始列表为空；第二步可以独立切换每本书的已读状态并删除指定书，允许同名书，操作一行不影响其他行。不要后端、网络和其他功能。'),
]
async def main():
    results=[]
    for name,topic in topics:
        row=repository.create_or_get('native_acceptance',str(uuid4()),topic)
        context=SimpleNamespace(task_id=row.current_job_id,owner_user_id='native_acceptance',
            is_cancel_requested=lambda:False,is_lease_valid=lambda:True,
            progress=lambda *args:print(name,*args,flush=True))
        started=time.monotonic();result={'name':name,'id':row.id};before=len(calls)
        try:
            await service.generate_exercise({'exercise_id':row.id,'topic':topic,'runtime_config_snapshot':{}},context,repository=repository)
            result['success']=True
        except Exception as exc:
            result.update(success=False,error=str(exc),code=getattr(exc,'code',None))
        saved=repository.get_owned('native_acceptance',row.id)
        (output/f'{name}-artifact.json').write_text(json.dumps(saved.artifact_public,ensure_ascii=False,indent=2))
        (output/f'{name}-private.json').write_text(json.dumps(saved.candidate_private or saved.checkpoint,ensure_ascii=False,indent=2))
        result.update(seconds=round(time.monotonic()-started,2),modelCalls=len(calls)-before)
        results.append(result);(output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False),flush=True)
    engine.dispose()
asyncio.run(main())
