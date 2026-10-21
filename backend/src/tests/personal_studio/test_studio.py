from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.api import personal_studio as api
from app.auth import get_current_user
from app.services.personal_studio import PersonalStudioTaskHandler, namespace, read
from app.services.generation_task_handlers import GenerationTaskHandler
from app.services.durable_task_handlers import DurableExecutionContext, DurableTaskExecutionError
from app.services.job_store import get_job
from app.services import platform_task_handlers
from app.chat.tasks.task_store import TaskStore
from core.config import Config
from core.course_storage import CourseStorageManager

@pytest.fixture
def setup(tmp_path, monkeypatch):
    for kind in ['JOB', 'TASK', 'COURSE', 'COURSE_MEMBERSHIP', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE']:
        monkeypatch.setenv(kind + '_PERSISTENCE_MODE', 'json')
    monkeypatch.setattr(Config, 'STORAGE_ROOT', tmp_path)
    storage = CourseStorageManager(root_path=str(tmp_path))
    store = TaskStore(tmp_path / 'tasks.sqlite3')
    monkeypatch.setattr(platform_task_handlers, 'get_task_store', lambda: store)
    monkeypatch.setattr(api.runtime_config_resolver, 'capture_snapshot', lambda owner: {})
    user = {'username': 'alice', 'role': 'student'}
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[api.manager] = lambda: storage
    app.dependency_overrides[api.learning_service] = lambda: FakeLearning()
    return TestClient(app), storage, store, user


class FakeLearning:
    prepared_courses = None
    def for_scope(self, owner, course): return self
    def require(self, course, owner):
        if course != 'course' or owner != 'alice': raise HTTPException(404, '无权访问')
    def room(self, course, owner, include_progress=False):
        self.require(course, owner)
        return {'title': 'Python 入门', 'goal': '掌握变量', 'chapters': [{'id': 'variables', 'title': '变量与类型', 'resources': [{'title': '变量正文', 'ready': True, 'remote': {'courseId': 'course', 'materialType': 'report', 'materialId': 'lesson', 'version': 3}}]}]}
    def material(self, *args): return {'version': 3, 'content': '课程实际内容：变量是名字到对象的绑定。', 'secret': 'do not include'}


def context(owner='alice', task='task-1', cancelled=False):
    return DurableExecutionContext(task_id=task, owner_user_id=owner, course_id=None,
        config_snapshot_id=None, progress=lambda *args: None, is_cancel_requested=lambda: cancelled)


class FakeGenerator:
    def __init__(self, kind): self.kind = kind
    def generate(self, payload, **kwargs):
        return {'artifacts': [{'artifact_type': self.kind, 'title': '学习资料', 'content': '# 实际内容' if self.kind == 'report' else {'cards': [{'front': '问题', 'back': '答案'}]}}]}


def handler(storage, kind='report', research=None):
    generator = GenerationTaskHandler(course_storage_manager=storage,
        service_factories={kind: lambda: FakeGenerator(kind)})
    return PersonalStudioTaskHandler(manager=storage, generator=generator, research=research)


def test_course_submission_is_durable_idempotent_and_owner_scoped(setup):
    client, storage, store, user = setup
    request = {'course_id': 'course', 'chapter_id': 'variables', 'request_id': 'first', 'title': '排序算法', 'resource_type': 'report', 'config': {}}
    first = client.post('/api/personal-studio/generate', json=request)
    assert first.status_code == 202, first.text
    job_id = first.json()['edu_job_id']
    assert first.json()['course_id'] == 'course'
    assert first.json()['input_summary']['studio_course_title'] == 'Python 入门'
    task = store.get_durable(job_id)
    assert task.workflow_type == 'personal_studio'
    assert task.command['course_id'] == namespace('alice')
    assert client.post('/api/personal-studio/generate', json=request).json()['edu_job_id'] == job_id
    assert client.post('/api/personal-studio/generate', json={**request, 'title': '不同主题'}).status_code == 409
    assert len(client.get('/api/personal-studio').json()['jobs']) == 1
    assert storage.list_course_infos() == []
    user['username'] = 'bob'
    assert client.get('/api/personal-studio').json()['jobs'] == []
    assert client.post('/api/personal-studio/generate', json=request).status_code == 404


@pytest.mark.parametrize('kind,config', [('report', {}), ('quiz', {'quiz_config': {'topic': '递归'}}), ('flashcard', {'flashcard_config': {'title': '递归'}}), ('graph', {'title': '递归'})])
def test_config_validation_and_forced_private_context(setup, kind, config):
    client, _, store, _ = setup
    request = {'course_id': 'course', 'chapter_id': 'variables', 'request_id': kind, 'title': '递归学习', 'resource_type': kind, 'config': {**config, 'course_id': '../bob', 'scope_id': 'stolen', 'source_mode': 'course_auto', 'selected_doc_ids': ['stolen']}}
    response = client.post('/api/personal-studio/generate', json=request)
    assert response.status_code == 202, response.text
    command = store.get_durable(response.json()['edu_job_id']).command
    assert command['source_mode'] == 'none'
    assert command['selected_doc_ids'] == []
    assert 'course_id' not in command['config']


@pytest.mark.parametrize('role', ['student', 'teacher', 'admin', 'user', ''])
@pytest.mark.parametrize('kind,config', [
    ('report', {}), ('quiz', {'quiz_config': {'topic': '递归'}}),
    ('flashcard', {'flashcard_config': {'title': '递归'}}), ('graph', {'title': '递归'}),
    ('podcast', {'topic': '递归', 'duration_minutes': 3}), ('scenario', {'topic': '递归'}),
])
def test_all_accounts_can_submit_every_studio_tool(setup, role, kind, config):
    client, _, store, user = setup
    user['role'] = role
    response = client.post('/api/personal-studio/generate', json={
        'course_id': 'course', 'chapter_id': 'variables', 'request_id': kind,
        'title': '递归学习', 'resource_type': kind, 'config': config,
    })
    assert response.status_code == 202, response.text
    assert store.get_durable(response.json()['edu_job_id']).command['resource_type'] == kind


def test_invalid_config_is_still_rejected(setup):
    client, _, _, _ = setup
    assert client.post('/api/personal-studio/generate', json={'course_id': 'course', 'chapter_id': 'variables', 'request_id': 'x', 'title': '闪卡', 'resource_type': 'flashcard', 'config': {'flashcard_config': {'count': 999}}}).status_code == 422


@pytest.mark.parametrize('kind', ['report', 'quiz', 'flashcard', 'graph'])
def test_generation_persists_without_course_and_readback_is_private(setup, kind):
    client, storage, _, user = setup
    run = {'resource_type': kind, 'source_mode': 'none', 'material_id': 'generated', 'config': {}, 'title': '排序', 'studio_mode': 'generate', 'course_id': 'attacker-supplied'}
    result = handler(storage, kind)(run, context(task="generated"))
    assert result['saved']
    assert result['result_ref']['resource_type'] == 'personal_resource'
    assert storage.list_course_infos() == []
    assert read('alice', kind, 'generated', storage)['source_job_id'] == 'generated'
    assert client.get('/api/personal-studio').json()['resources'][0]['studio_title'] == '排序'
    assert client.get(f'/api/personal-studio/resources/{kind}/generated').json()['course_id'] is None
    user['username'] = 'bob'
    assert client.get(f'/api/personal-studio/resources/{kind}/generated').status_code == 404
    assert client.get('/api/personal-studio').json()['resources'] == []


def test_research_is_one_report_with_sources(setup):
    client, storage, _, _ = setup
    called = []
    def research(**kwargs):
        called.append(kwargs)
        return {'ok': True, 'results': [{'title': '真实来源', 'url': 'https://example.org/research', 'content': '证据内容'}]}
    result = handler(storage, research=research)({'resource_type': 'report', 'source_mode': 'none', 'material_id': 'research', 'config': {}, 'title': '研究问题', 'studio_mode': 'research'}, context(task='research'))
    assert result['saved'] and called[0]['save_to_kb'] is False
    assert read('alice', 'report', 'research', storage)['research_sources'][0]['content'] == '证据内容'
    assert len(client.get('/api/personal-studio').json()['resources']) == 1


def test_empty_search_does_not_create_fictional_report(setup):
    _, storage, _, _ = setup
    with pytest.raises(DurableTaskExecutionError, match='没有找到'):
        handler(storage, research=lambda **kw: {'results': []})({'resource_type': 'report', 'title': '问题', 'studio_mode': 'research'}, context(task='research'))
    assert storage.list_generated_materials(namespace('alice'), aggregate=True) == []


def test_cancel_does_not_publish_result(setup):
    _, storage, _, _ = setup
    result = handler(storage)({'resource_type': 'report', 'source_mode': 'none', 'material_id': 'cancelled', 'title': '取消', 'config': {}}, context(cancelled=True))
    assert result['canceled']
    with pytest.raises(HTTPException): read('alice', 'report', 'cancelled', storage)


def test_attach_is_an_explicit_idempotent_private_copy(setup, monkeypatch, tmp_path):
    client, storage, _, user = setup
    for key in ('LEARNING_SESSION_V1_ENABLED', 'LEARNING_AGENT_V1_ENABLED', 'LEARNING_ENRICHMENT_V1_ENABLED',
                'LEARNING_PREPARATION_V1_ENABLED', 'LEARNING_PROGRESS_V1_ENABLED', 'COURSE_PREPARATION_ENABLED'):
        monkeypatch.setenv(key, 'false')
    from app.self_learning import service as learning_module
    from app.self_learning.store import LearningStore
    from app.services.course_membership_store import CourseMembershipStore
    storage.create_course_structure('course')
    storage.save_course_info('course', {'id': 'course', 'title': 'Python', 'created_by': 'alice'})
    storage.save_knowledge_graph('course', {'root': {'id': 'root', 'children': [{'id': 'a', 'label': '变量'}]}})
    members = CourseMembershipStore(tmp_path / 'members.json')
    members.upsert('course', 'alice', 'owner', added_by='alice')
    learning = learning_module.LearningService(manager=storage, store=LearningStore(tmp_path / 'learning'), memberships=members)
    monkeypatch.setattr(learning_module, 'LearningService', lambda: learning)
    handler(storage)({'resource_type': 'report', 'source_mode': 'none', 'material_id': 'resource', 'title': '变量说明', 'config': {}}, context(task='resource'))
    path = '/api/personal-studio/resources/report/resource/attach'
    assert client.post(path, json={'course_id': 'course', 'chapter_id': 'missing'}).status_code == 422
    assert client.post(path, json={'course_id': 'other', 'chapter_id': 'a'}).status_code == 404
    payload = {'course_id': 'course', 'chapter_id': 'a'}
    first = client.post(path, json=payload)
    assert first.status_code == 200, first.text
    second = client.post(path, json=payload)
    first_ids = [r['id'] for c in first.json()['chapters'] for r in c['resources']]
    assert [r['id'] for c in second.json()['chapters'] for r in c['resources']] == first_ids
    assert read('alice', 'report', 'resource', storage)['content'] == '# 实际内容'
    assert all(m['visibility'] == 'private' for m in storage.list_generated_materials('course', aggregate=True, owner_user_id='alice'))
    user['username'] = 'bob'
    assert client.post(path, json=payload).status_code == 404


def test_completion_requires_finished_owner_resource(setup):
    _, storage, store, _ = setup
    from app.services.job_completion_service import JobCompletionService
    completion = JobCompletionService(task_store=store, course_storage_manager=storage)
    task = SimpleNamespace(owner_user_id='alice', task_id='generated')
    ref = {'resource_type': 'personal_resource', 'material_type': 'report', 'material_id': 'generated'}
    assert completion._verify_result(task, ref)[0] == 'RESOURCE_READBACK_FAILED'
    handler(storage)({'resource_type': 'report', 'source_mode': 'none', 'title': '排序', 'config': {}}, context(task='generated'))
    assert completion._verify_result(task, ref) == (None, '')
    assert completion._verify_result(SimpleNamespace(owner_user_id='bob', task_id='generated'), ref)[0] == 'RESOURCE_READBACK_FAILED'


def test_research_partial_write_is_not_listed_or_recovered_as_complete(setup):
    client, storage, store, _ = setup
    from app.services.job_reconciliation_service import JobReconciliationService
    # A direct generator can write before the research wrapper stores sources.
    storage.save_generated_material(namespace('alice'), 'report', 'partial', {'title': '未完成', 'content': '正文'}, owner_user_id='alice', source_job_id='partial')
    assert client.get('/api/personal-studio').json()['resources'] == []
    reconciler = JobReconciliationService(task_store=store, course_storage_manager=storage)
    task = SimpleNamespace(status='leased', cancel_requested=False, deadline_at=None, command={'resource_type': 'report', 'course_id': namespace('alice'), 'material_id': 'partial'}, course_id=None, owner_user_id='alice', task_id='partial', workflow_type='personal_studio')
    assert reconciler._published_result_ref(task, now=0) is None
    storage.save_generated_material(namespace('alice'), 'report', 'partial', {'studio_complete': True}, owner_user_id='alice')
    assert reconciler._published_result_ref(task, now=0)['resource_type'] == 'personal_resource'


def test_course_is_required_and_other_nodes_are_rejected(setup):
    client, _, _, _ = setup
    request = {'request_id': 'context', 'title': '变量报告'}
    assert client.post('/api/personal-studio/generate', json=request).status_code == 422
    assert client.post('/api/personal-studio/generate', json={**request, 'course_id': 'other', 'chapter_id': 'variables'}).status_code == 404
    assert client.post('/api/personal-studio/generate', json={**request, 'course_id': 'course', 'chapter_id': 'missing'}).status_code == 422


def test_frozen_course_content_reaches_generator_and_resource(setup):
    client, storage, store, _ = setup
    response = client.post('/api/personal-studio/generate', json={'request_id': 'bound', 'title': '变量报告', 'course_id': 'course', 'chapter_id': 'variables', 'config': {'research_context': '伪造内容', 'studio_course_title': '伪造课程'}})
    assert response.status_code == 202, response.text
    job_id = response.json()['edu_job_id']
    command = store.get_durable(job_id).command
    assert '名字到对象' in command['config']['research_context']
    assert '伪造' not in str(command)
    assert 'do not include' not in str(command)
    observed = []
    class BoundGenerator(FakeGenerator):
        def generate(self, payload, **kwargs):
            observed.append(payload.research_context)
            return super().generate(payload, **kwargs)
    generator = GenerationTaskHandler(course_storage_manager=storage, service_factories={'report': lambda: BoundGenerator('report')})
    result = PersonalStudioTaskHandler(manager=storage, generator=generator, learning_factory=FakeLearning)(command, context(task=job_id))
    assert result['saved'] and '名字到对象' in observed[0]
    resource = client.get(f'/api/personal-studio/resources/report/{job_id}').json()
    assert resource['course_id'] == 'course'
    assert resource['studio_course_title'] == 'Python 入门'
    assert resource['studio_chapter_title'] == '变量与类型'
    assert resource['studio_source_refs'][0]['version'] == 3
    assert client.get('/api/personal-studio').json()['resources'][0]['studio_course_id'] == 'course'
    assert client.post(f'/api/personal-studio/resources/report/{job_id}/attach', json={'course_id': 'other', 'chapter_id': 'a'}).status_code == 422


def test_version_change_blocks_context_and_revoked_access_blocks_execution(setup):
    from app.services.personal_studio import course_context
    class Changed(FakeLearning):
        def material(self, *args): return {'version': 4, 'content': 'new content'}
    with pytest.raises(HTTPException) as error: course_context('alice', 'course', 'variables', Changed())
    assert error.value.status_code == 409
    _, storage, _, _ = setup
    class Revoked(FakeLearning):
        def require(self, *args): raise HTTPException(404, 'no longer allowed')
    with pytest.raises(HTTPException):
        PersonalStudioTaskHandler(manager=storage, learning_factory=Revoked)({'title': '变量报告', 'studio_context': course_context('alice', 'course', 'variables', FakeLearning())}, context())


def test_research_keeps_course_context_and_searches_with_course_scope(setup):
    from app.services.personal_studio import course_context
    _, storage, _, _ = setup
    seen = []
    class BoundGenerator(FakeGenerator):
        def generate(self, payload, **kwargs):
            assert '名字到对象' in payload.research_context
            assert '外部证据' in payload.final_user_prompt
            return super().generate(payload, **kwargs)
    generator = GenerationTaskHandler(course_storage_manager=storage, service_factories={'report': lambda: BoundGenerator('report')})
    def research(**kwargs):
        seen.append(kwargs['query'])
        return {'results': [{'url': 'https://example.org', 'content': '外部证据'}]}
    result = PersonalStudioTaskHandler(manager=storage, generator=generator, research=research, learning_factory=FakeLearning)({'resource_type': 'report', 'title': '命名规则', 'studio_mode': 'research', 'studio_context': course_context('alice', 'course', 'variables', FakeLearning())}, context())
    assert result['saved']
    assert 'Python 入门' in seen[0] and '变量与类型' in seen[0]


def test_research_sources_readable_before_conclusion_and_collection_is_reference_only(setup):
    client, storage, store, user = setup
    response = client.post('/api/personal-studio/generate', json={'request_id': 'live-research', 'title': '变量应用研究', 'course_id': 'course', 'chapter_id': 'variables', 'mode': 'research'})
    assert response.status_code == 202, response.text
    job_id = response.json()['edu_job_id']
    command = store.get_durable(job_id).command
    assert client.get(f'/api/personal-studio/research/{job_id}').json()['sources'] == []
    generator = GenerationTaskHandler(course_storage_manager=storage, service_factories={'report': lambda: FakeGenerator('report')})
    def during_generation(run, ctx):
        progress = client.get(f'/api/personal-studio/research/{job_id}').json()
        assert progress['resource'] is None
        assert progress['sources'][0]['content'] == '可立即阅读的正文'
        assert client.put(f'/api/personal-studio/resources/report/{job_id}/library', json={'saved': True}).status_code == 409
        assert client.get('/api/personal-studio').json()['resources'] == []
        return generator(run, ctx)
    def research(**kwargs):
        assert kwargs['persist_batch'] is False and kwargs['save_to_kb'] is False
        return {'results': [{'url': 'https://example.org', 'title': '来源', 'content': '可立即阅读的正文'}]}
    PersonalStudioTaskHandler(manager=storage, generator=during_generation, research=research, learning_factory=FakeLearning)(command, context(task=job_id))
    result = client.get(f'/api/personal-studio/research/{job_id}').json()
    assert result['resource']['studio_library_saved'] is False
    url = f'/api/personal-studio/resources/report/{job_id}/library'
    first = client.put(url, json={'saved': True})
    assert first.status_code == 200 and first.json()['studio_library_saved'] is True
    assert client.put(url, json={'saved': True}).json()['version'] == first.json()['version']
    assert len(storage.list_generated_materials(namespace('alice'), owner_user_id='alice', space='mine', aggregate=True)) == 1
    assert client.put(url, json={'saved': False}).json()['studio_library_saved'] is False
    assert client.get(f'/api/personal-studio/research/{job_id}').json()['resource']['content'] == '# 实际内容'
    user['username'] = 'bob'
    assert client.get(f'/api/personal-studio/research/{job_id}').status_code == 404
    assert client.put(url, json={'saved': True}).status_code == 404
