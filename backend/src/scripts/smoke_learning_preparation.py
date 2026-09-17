"""Real model produces/revises synthetic personal resources in an isolated schema."""
import asyncio
import json
import os
from pathlib import Path
import time
from uuid import uuid4
TEST_URL=os.environ['LEARNING_TEST_DATABASE_URL']
from app.services.runtime_config_resolver import runtime_config_resolver
config=runtime_config_resolver.resolve('llm')
os.environ['LEARNING_TEST_DATABASE_URL']=TEST_URL
os.environ['LEARNING_BROWSER_AGENT']='1'
os.environ['LEARNING_BROWSER_ENRICHMENT']='1'
os.environ['LEARNING_BROWSER_PREPARATION']='1'
from tests.self_learning import browser_app as fixture
from sqlalchemy import text
from app.chat.bounded_completion import BoundedModelAdapter, answer_json
from app.self_learning.turn_contracts import AnswerRequest
from app.self_learning.agent_runtime import LearningAgentRuntime

svc=fixture.svc
adapter=BoundedModelAdapter.from_config(config)
async def production(owner,system,data,snapshot):
    reply=await adapter.complete([{'role':'system','content':system},{'role':'user','content':json.dumps(data,ensure_ascii=False)}],[],deadline=time.monotonic()+45)
    if reply['calls']:
        raise ValueError('unexpected tools')
    return answer_json(reply['content'])
svc.preparations.service.model_json=production
runtime=LearningAgentRuntime(svc,svc.turn_repository,lambda _:adapter)
report={'model':config['model'],'database':'isolated PostgreSQL schema','tasks':[]}
try:
    fixture.manager.save_generated_material('learning-fixture','report','a-core',{'title':'Python变量','content':'# 变量\n\nx = 1 将整数 1 绑定给名称 x。随后 x = 2 会重新绑定 x。赋值不是数学等式。'},owner_user_id='alice',visibility='course',scope_type='knowledge_point',scope_id='a')
    ref={'course_id':'learning-fixture','material_type':'report','material_id':'a-core','version':2}
    for question in ('请生成并保存一份变量赋值的补充文档，包含追踪两个变量的例子和常见误区。','请修改当前这份文档，增加一个交换两个变量的例子，保存为个人版本。'):
        start=time.monotonic()
        accepted=svc.turns.accept('alice','learning-fixture','a',AnswerRequest(request_id=uuid4(),question=question,reading_context={'resource_ref':ref}))
        runtime.run_once()
        answer=svc.turns.get('alice',accepted['turn_id'])
        effects=[e for e in answer.get('committed_effects',[]) if e['kind']=='preparation']
        item={'question':question,'answer':answer,'seconds':None}
        report['tasks'].append(item)
        if not effects:
            raise RuntimeError('real tutor did not submit preparation')
        svc.preparations.service.run_once()
        task=svc.preparations.get('alice',effects[0]['preparation_id'])
        item['task']=task
        item['seconds']=round(time.monotonic()-start,2)
        if task['status']!='succeeded':
            raise RuntimeError('real preparation failed')
        resource=task['result']['resource_refs'][0]
        ref={k:resource[k] for k in ('course_id','material_type','material_id','version')}
        material=svc.material('learning-fixture',ref['material_type'],ref['material_id'],'alice')
        item['material']={k:material.get(k) for k in ('title','content','source_ref','visibility','version')}
        assert material['visibility']=='private'
        svc.preparations.notifications.drain()
        print(json.dumps({'status':task['status'],'seconds':item['seconds'],'operation':task['operation']},ensure_ascii=False),flush=True)
        assert answer['status']=='succeeded',answer['error_code']
finally:
    destination=Path(__file__).resolve().parents[3]/'docs/acceptance/artifacts/learning-agent-p5/real-model.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    fixture.engine.dispose()
    with fixture.admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA {fixture.schema} CASCADE'))
    fixture.admin.dispose()
