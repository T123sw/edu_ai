"""Isolated P1 browser fixture: real learning routes/DB, deterministic model/auth.

Launch only with explicit LEARNING_TEST_DATABASE_URL. Never loads a business DB.
"""
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from contextlib import asynccontextmanager

test_url = os.environ['LEARNING_TEST_DATABASE_URL']
real_model_config = None
if os.getenv('LEARNING_BROWSER_REAL') == '1':
    from app.services.runtime_config_resolver import runtime_config_resolver
    real_model_config = runtime_config_resolver.resolve('llm')
    os.environ['LEARNING_TEST_DATABASE_URL'] = test_url
root = Path(tempfile.mkdtemp(prefix='learning-p1-browser-'))
# Legacy Config uses load_dotenv(override=True). Disable it inside this fixture
# process before importing application modules, and pin every storage boundary.
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
os.environ['DATABASE_URL'] = test_url
for domain in ['APP_STATE', 'MATERIAL', 'KNOWLEDGE', 'COURSE', 'COURSE_MEMBERSHIP', 'USER', 'JOB', 'CONVERSATION']:
    os.environ[domain + '_PERSISTENCE_MODE'] = 'json'
os.environ['STORAGE_ROOT'] = str(root / 'storage')

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from app.database import Base
from app.api.self_learning import router, service
from app.auth import get_current_user
from app.self_learning.postgres_repository import SessionRepository
from app.self_learning.progress_repository import ProgressRepository, TABLES
from app.self_learning.turn_repository import TurnRepository
from app.self_learning.agent_runtime import LearningAgentRuntime
from app.self_learning.turn_contracts import AgentFailure
import asyncio
from app.self_learning.service import LearningService
from app.self_learning.store import LearningStore
from app.services.course_membership_store import CourseMembershipStore
from core.course_storage import CourseStorageManager

schema = 'learning_browser_' + uuid4().hex
admin = create_engine(test_url)
with admin.begin() as conn:
    conn.execute(text(f'CREATE SCHEMA {schema}'))
engine = create_engine(test_url, connect_args={'options': f'-csearch_path={schema}'})
Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in (
    'conversations', 'conversation_messages', 'learning_topic_sessions', 'learning_agent_turns', 'learning_answer_runs', 'learning_agent_tool_calls', 'learning_agent_outbox', *TABLES)])
manager = CourseStorageManager(root_path=str(root / 'courses'))
manager.create_course_structure('learning-fixture')
manager.save_course_info('learning-fixture', {'id': 'learning-fixture', 'title': '会话测试课程', 'created_by': 'alice'})
manager.save_knowledge_graph('learning-fixture', {'root': {'id': 'root', 'children': [
    {'id': 'a', 'label': '节点 A'}, {'id': 'b', 'label': '节点 B'}, {'id': 'c', 'label': '长历史'}]}})
members = CourseMembershipStore(root / 'members.json')
for owner in ('alice', 'bob'):
    members.upsert('learning-fixture', owner, 'owner', added_by=owner)
for node, mid, title in [('a', 'a-core', '节点 A 核心文档'), ('a', 'a-extra', '节点 A 补充文档'), ('b', 'b-core', '节点 B 核心文档'), ('c', 'c-core', '长历史文档')]:
    manager.save_generated_material('learning-fixture', 'report', mid,
        {'title': title, 'learning_course_resource': True, 'content': '# ' + title + '\n\n' + ('测试正文。\n\n' * 100)},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id=node)


class Model:
    failed_once = set()
    async def complete(self, messages, tools, deadline):
        import json
        question = messages[-1]['content']
        if os.getenv('LEARNING_BROWSER_PREPARATION') == '1':
            if messages[-1]['role'] == 'tool':
                return {'calls': [], 'content': json.dumps({'answer_markdown':'准备任务已接收，可以继续学习，完成后从资料准备通知打开。','citation_ids':[]})}
            if '生成并保存' in question or '修改当前' in question:
                return {'content':'','calls':[{'id':'prepare','type':'function','function':{'name':'submit_preparation_request',
                    'arguments':json.dumps({'operation':'revise_resource' if '修改当前' in question else 'supplement_node','goal':question,'resource_types':['report']})}}]}
        if '慢回答' in question:
            await asyncio.sleep(2)
        if '一次失败' in question and question not in self.failed_once:
            self.failed_once.add(question)
            raise AgentFailure('MODEL_UNAVAILABLE')
        if '模型失败' in question:
            raise AgentFailure('MODEL_UNAVAILABLE')
        return {'calls': [], 'content': json.dumps({'answer_markdown': '已回答：' + question, 'citation_ids': ['ctx_01']}, ensure_ascii=False)}
    def chat(self, messages, **kwargs):
        import time
        question = messages[-1]['content']
        if '慢回答' in question:
            time.sleep(2)
        if '模型失败' in question:
            raise RuntimeError('fixture model unavailable')
        return '已回答：' + question


svc = LearningService(manager=manager, store=LearningStore(root), memberships=members,
    model_factory=lambda _: Model(), session_repository=SessionRepository(engine), progress_repository=ProgressRepository(engine), turn_repository=TurnRepository(engine) if os.getenv('LEARNING_BROWSER_AGENT') == '1' else None)
if os.getenv('LEARNING_BROWSER_ENRICHMENT') == '1':
    from app.self_learning.enrichment_models import TABLES as ENRICHMENT_TABLES
    from app.self_learning.check_service import CheckService
    from app.self_learning.memory_adapter import MemoryAdapter
    from app.self_learning.summary_service import SummaryService
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in (
        'agent_memory_items', 'user_profile_facts', 'agent_memory_audit_events', *ENRICHMENT_TABLES)])
    async def check_generator(data):
        return {'form': 'choice', 'stem': '哪一个是变量赋值？', 'options': [
            {'id':'option_1','text':'x = 1'}, {'id':'option_2','text':'print(x)'}],
            'correct_option_ids':['option_1'], 'reference_answer':'', 'explanation':'赋值把值绑定给变量。'}
    svc.checks = CheckService(svc, engine, generator=check_generator)
    svc.memory = MemoryAdapter(svc, engine)
    svc.summaries = SummaryService(svc, engine, svc.memory)
    svc.progress_service.repository.evidence_reader = svc.checks.evidence
if os.getenv('LEARNING_BROWSER_PREPARATION') == '1':
    from app.course_preparation.production_models import TABLES as PRODUCTION_TABLES
    from app.course_preparation.production_service import ProductionService
    from app.self_learning.preparation_adapter import PreparationAdapter
    from app.database import User
    from sqlalchemy.orm import Session
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in (
        'users','course_preparations','course_preparation_attempts','course_preparation_events',*PRODUCTION_TABLES)])
    with Session(engine) as db, db.begin():
        for name in ('alice','bob'):
            db.add(User(user_id='fixture-'+name, username=name, password_hash='fixture-only', role='student'))
    async def production_model(owner, system, data, snapshot):
        if '检查者' in system:
            return {'passed':True,'issues':[]}
        await asyncio.sleep(3)
        return {'title':'个人变量例子','content':'# 变量的新例子\n\n' + '例如先执行 x = 1，再执行 x = 2，x 的值变成 2。赋值会改变名称所绑定的值，和数学上的等式不同。可以逐行追踪变量，检查自己的理解。' * 3}
    svc.preparations = PreparationAdapter(svc, ProductionService(svc, engine, model_json=production_model))
if os.getenv('LEARNING_BROWSER_ACCEPTANCE') == '1':
    manager.save_generated_material('learning-fixture','quiz','a-quiz',{'title':'变量版本化练习','learning_course_resource':True,
        'questions':[{'form':'choice','stem':'执行 x = 1 后 x 是多少？','options':[{'id':'one','text':'整数 1'},{'id':'two','text':'整数 2'}],
            'correct_option_ids':['one'],'explanation':'赋值将整数 1 绑定给 x。'}]},owner_user_id='alice',visibility='course',scope_type='knowledge_point',scope_id='a')
    manager.save_generated_material('learning-fixture','classroom','b-classroom',{'title':'变量交互课堂','learning_course_resource':True,
        'scenes':[{'id':f'scene-{i}','type':'interactive','title':f'变量场景{i}','content':{'type':'interactive','html':f'<h1>变量场景{i}</h1><p>x = {i}</p>'},'actions':[]} for i in (1,2)]},
        owner_user_id='alice',visibility='course',scope_type='knowledge_point',scope_id='b')
if real_model_config:
    from app.chat.bounded_completion import BoundedModelAdapter,answer_json
    import json,time,httpx
    model_diagnostics=[]
    async def diagnose(response):
        await response.aread()
        try:
            data=response.json()
            model_diagnostics.append({'status':response.status_code,'usage':data.get('usage'),
                'choices':[{'finish_reason':c.get('finish_reason'),'content':c.get('message',{}).get('content'),
                    'tool_calls':c.get('message',{}).get('tool_calls')} for c in data.get('choices',[])]})
            destination=Path(__file__).resolve().parents[4]/'docs/acceptance/artifacts/learning-agent-p6/real-browser-transport.json'
            destination.write_text(json.dumps(model_diagnostics,ensure_ascii=False,indent=2))
        except (ValueError,OSError):
            pass
    real_adapter=BoundedModelAdapter.from_config(real_model_config,lambda **kw:httpx.AsyncClient(event_hooks={'response':[diagnose]},**kw))
    async def real_json(owner,system,data,snapshot=None):
        response=await real_adapter.complete([{'role':'system','content':system},{'role':'user','content':json.dumps(data,ensure_ascii=False)}],[],deadline=time.monotonic()+45)
        return answer_json(response['content'])
    svc.preparations.service.model_json=real_json
    svc.checks.generator=None
    svc.checks.model_json=real_json
    manager.save_generated_material('learning-fixture','report','a-core',{'title':'Python变量与赋值','content':'# 变量与赋值\n\nx = 1 将整数 1 绑定给 x。随后 x = 2 重新绑定 x。y = x 让 y 引用 x 当前绑定的对象，不是复制对象。\n\n变量名与值应区分，赋值不是数学等式。','learning_course_resource':True},owner_user_id='alice',visibility='course',scope_type='knowledge_point',scope_id='a')
# Explicit requirement fixture exercises P0 manifest projection through the real P2 API.
manager.create_course_structure('manifest-fixture')
manager.save_course_info('manifest-fixture', {'id': 'manifest-fixture', 'title': '核心与可选资料', 'created_by': 'alice'})
manager.save_knowledge_graph('manifest-fixture', {'root': {'id': 'root', 'children': [{'id': 'a', 'label': '核心节点'}, {'id': 'b', 'label': '下一节点'}]}})
for owner in ('alice', 'bob'):
    members.upsert('manifest-fixture', owner, 'owner', added_by=owner)
for mid, node in [('core', 'a'), ('extra', 'a'), ('next', 'b')]:
    manager.save_generated_material('manifest-fixture', 'report', mid, {'title': mid, 'content': '# ' + mid, 'learning_course_resource': True},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id=node)
manifest = {'course_id': 'manifest-fixture', 'manifest_id': 'fixture-manifest', 'version': 1, 'route_version': 1,
    'nodes': [{'node_id': node, 'title': node, 'resources': [{'resource_type': 'report', 'resource_id': mid, 'version': 1, 'required': mid != 'extra'}
        for mid, target in [('core', 'a'), ('extra', 'a'), ('next', 'b')] if target == node]} for node in ('a', 'b')]}
svc.progress_service.reader.load_manifest = lambda actor, course, ref: manifest if course == 'manifest-fixture' else None

svc.session_repository.ensure_session('alice', 'learning-fixture', 'c', '长历史导学', [
    {'turn_id': f'legacy-{i}', 'question': f'历史问题{i}', 'answer_text': f'历史回答{i}', 'resource_id': 'c-core'}
    for i in range(150)])


@asynccontextmanager
async def lifespan(app):
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: real_adapter if real_model_config else Model()) if svc.turn_repository else None
    if runtime:
        runtime.start()
    yield
    if runtime:
        runtime.stop()
    engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5196'], allow_methods=['*'], allow_headers=['*'])


def fixture_user(authorization: str = Header(default='')):
    owner = authorization.removeprefix('Bearer ')
    if owner not in {'alice', 'bob'}:
        raise HTTPException(401, 'test identity required')
    return {'username': owner, 'role': 'student'}


@app.post('/api/auth/verify')
def verify(authorization: str = Header(default='')):
    return {'valid': True, 'user': fixture_user(authorization)}


@app.get('/api/self-learning/state')
def overview(authorization: str = Header(default='')):
    owner = fixture_user(authorization)['username']
    return {'version': 1, 'rooms': [svc.room('learning-fixture', owner), svc.room('manifest-fixture', owner)], 'resources': [], 'jobs': [], 'serverJobs': [], 'shared': []}


@app.get('/api/courses/{course}/materials/{kind}/{mid}')
def material(course: str, kind: str, mid: str, authorization: str = Header(default='')):
    return svc.material(course, kind, mid, fixture_user(authorization)['username'])


app.dependency_overrides[get_current_user] = fixture_user
app.dependency_overrides[service] = lambda: svc
app.include_router(router)


@app.get('/api/courses/{course}/classrooms/{mid}')
def classroom_material(course: str, mid: str, resource_version: int, authorization: str = Header(default='')):
    from app.self_learning.resource_reader import exact_material
    from app.self_learning.contracts import ResourceRef
    return exact_material(svc,fixture_user(authorization)['username'],ResourceRef(course_id=course,material_type='classroom',material_id=mid,version=resource_version))
