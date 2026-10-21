"""Real-model PBL acceptance against a fresh SQLite repository and isolated config.

Usage: python scripts/pbl/runtime_acceptance_generate.py /tmp/pbl-native-run
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
    ('node-read','使用 Node.js 和 Express 做一个无请求体的 HTTP 查询服务，分两步：第一步 GET /health 返回 JSON {status:"ok"}；第二步 GET /square?n=数字 返回 JSON {result:平方值}，缺少 n 或不是有效数字时返回 400 和 JSON {error:"invalid n"}。只使用 GET，不用 POST、数据库或网络，计算函数与路由分文件。'),
    ('vanilla','使用原生 HTML、CSS 和 JavaScript 做一个本地温度换算器，不使用 React 或其他框架，分两步：第一步输入摄氏温度点击换算后显示华氏温度，0 摄氏显示 32；第二步增加重置按钮恢复空输入和空结果。输入与转换逻辑拆到不同文件，不用外部 API。'),
    ('vue','使用 Vue 3 做一个本地活动报名页，不使用 React，分两步：第一步姓名为空或仅空格时禁用报名按钮；第二步提交有效姓名后显示报名成功和姓名，点击重新填写清空输入与结果。不要网络和后端。'),
    ('node','使用 Node.js 和 Express 做一个内存备忘录 HTTP API，不做 React 页面，不使用真实数据库或外部服务。分两步：第一步 GET /notes 返回初始空数组；第二步 POST /notes 接收 JSON {id:字符串,text:字符串} 保存条目，返回 201 和保存对象，之后 GET /notes 返回已保存数组。id 由请求指定，路由与数据逻辑拆文件。'),
    ('react-ts','使用 React 和 TypeScript 做一个本地打字统计器，分两步：第一步输入文本即时显示包含空格的字符数，初始 0；第二步增加清空按钮，清空后输入为空、数量为 0。统计逻辑拆成独立 TypeScript 文件，不要网络。'),
]

if len(sys.argv)>2:topics=[item for item in topics if item[0] in sys.argv[2:]]
async def main():
    results=[]
    for name,topic in topics:
        row=repository.create_or_get('runtime_acceptance',str(uuid4()),topic)
        context=SimpleNamespace(task_id=row.current_job_id,owner_user_id='runtime_acceptance',
            is_cancel_requested=lambda:False,is_lease_valid=lambda:True,
            progress=lambda *args:print(name,*args,flush=True))
        started=time.monotonic();result={'name':name,'id':row.id};before=len(calls)
        try:
            await service.generate_exercise({'exercise_id':row.id,'topic':topic,'runtime_config_snapshot':{}},context,repository=repository)
            result['success']=True
        except Exception as exc:
            result.update(success=False,error=str(exc),code=getattr(exc,'code',None))
        saved=repository.get_owned('runtime_acceptance',row.id)
        (output/f'{name}-artifact.json').write_text(json.dumps(saved.artifact_public,ensure_ascii=False,indent=2))
        (output/f'{name}-private.json').write_text(json.dumps(saved.candidate_private or saved.checkpoint,ensure_ascii=False,indent=2))
        result['runtime']=(saved.artifact_public or {}).get('runtime')
        result.update(seconds=round(time.monotonic()-started,2),modelCalls=len(calls)-before)
        results.append(result);(output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False),flush=True)
    engine.dispose()
asyncio.run(main())
