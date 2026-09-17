"""Isolated P1 browser fixture: real learning routes/DB, deterministic model/auth.

Launch only with explicit LEARNING_TEST_DATABASE_URL. Never loads a business DB.
"""
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from contextlib import asynccontextmanager

test_url = os.environ['LEARNING_TEST_DATABASE_URL']
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
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: Model()) if svc.turn_repository else None
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
