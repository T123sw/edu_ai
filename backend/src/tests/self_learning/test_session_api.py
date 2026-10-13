import hashlib
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from app.api.self_learning import router, service as service_dependency
from app.auth import get_current_user
from app.self_learning.service import LearningService
from app.self_learning.store import LearningStore
from app.services.course_membership_store import CourseMembershipStore
from core.course_storage import CourseStorageManager
from tests.self_learning.test_session_repository import repository


@pytest.fixture
def live_service(repository, tmp_path, monkeypatch):
    # This session fixture creates only session tables. Later fixtures explicitly
    # install their own agent/progress services; production .env flags must not
    # auto-wire those services (or connect this fixture to the business database).
    for key in ('LEARNING_AGENT_V1_ENABLED', 'LEARNING_ENRICHMENT_V1_ENABLED',
                'LEARNING_PREPARATION_V1_ENABLED', 'LEARNING_PROGRESS_V1_ENABLED',
                'COURSE_PREPARATION_ENABLED'):
        monkeypatch.setenv(key, 'false')
    for key in ['APP_STATE', 'MATERIAL', 'KNOWLEDGE', 'COURSE', 'COURSE_MEMBERSHIP']:
        monkeypatch.setenv(key + '_PERSISTENCE_MODE', 'json')
    manager = CourseStorageManager(root_path=str(tmp_path / 'courses'))
    manager.create_course_structure('course')
    manager.save_course_info('course', {'id': 'course', 'title': 'Python', 'created_by': 'alice'})
    manager.save_knowledge_graph('course', {'root': {'id': 'root', 'children': [{'id': 'a', 'label': '变量'}, {'id': 'b', 'label': '条件'}]}})
    members = CourseMembershipStore(tmp_path / 'members.json')
    for user in ('alice', 'bob'):
        members.upsert('course', user, 'owner' if user == 'alice' else 'viewer', added_by='alice')
    class Model:
        calls = []
        def chat(self, messages, **kwargs):
            self.calls.append(messages)
            return '变量保存值。'
    model = Model()
    svc = LearningService(manager=manager, store=LearningStore(tmp_path), memberships=members,
                          model_factory=lambda _: model, session_repository=repository)
    svc.test_model = model
    return svc


@pytest.fixture
def client(live_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[service_dependency] = lambda: live_service
    def user(x_user: str = Header(default='alice')):
        return {'username': x_user, 'role': 'student'}
    app.dependency_overrides[get_current_user] = user
    with TestClient(app) as client:
        yield client


BASE = '/api/self-learning/courses/course/topics/'


def test_read_does_not_create_and_enter_is_stable(client, live_service):
    assert client.get(BASE + 'a/session').status_code == 404
    assert live_service.session_repository.find('alice', 'course', 'a') is None
    first = client.post(BASE + 'a/enter').json()
    assert first['message_count'] == 1
    assert client.post(BASE + 'a/enter').json()['session_id'] == first['session_id']
    second = client.post(BASE + 'b/enter').json()
    assert second['session_id'] != first['session_id']
    assert client.post(BASE + 'a/enter', headers={'x-user': 'bob'}).json()['session_id'] != first['session_id']
    assert client.post(BASE + 'a/enter', headers={'x-user': 'outsider'}).status_code == 404
    assert client.post(BASE + 'absent/enter').status_code == 404
    assert client.get(BASE + 'a/session?limit=101').status_code == 422
    live_service.manager.save_knowledge_graph('course', {'root': {'id': 'root', 'children': [{'id': 'b', 'label': '改名B'}, {'id': 'a', 'label': '改名A'}]}})
    assert client.post(BASE + 'a/enter').json()['session_id'] == first['session_id']


def test_answer_persists_once_failure_recovers_and_context_isolated(client, live_service):
    payload = {'question': '独有问题A', 'request_id': str(uuid4()), 'resource_id': 'pending:a'}
    assert client.post(BASE + 'a/turns', json=payload).status_code == 200
    assert client.post(BASE + 'a/turns', json=payload).status_code == 200
    assert len(live_service.test_model.calls) == 1
    assert client.post(BASE + 'a/turns', json={**payload, 'question': 'changed'}).status_code == 409
    assert len(client.get(BASE + 'a/session').json()['items']) == 3
    assert client.post(BASE + 'b/turns', json={**payload, 'request_id': str(uuid4()), 'resource_id': 'pending:b', 'question': '条件'}).status_code == 200
    assert '独有问题A' not in json.dumps(live_service.test_model.calls[-1], ensure_ascii=False)
    class Broken:
        def chat(self, *args, **kwargs):
            raise RuntimeError('failure')
    factory = live_service.model_factory
    live_service.model_factory = lambda _: Broken()
    retry = {**payload, 'request_id': str(uuid4()), 'question': 'failed question'}
    assert client.post(BASE + 'a/turns', json=retry).status_code == 502
    assert len(client.get(BASE + 'a/session').json()['items']) == 4
    live_service.model_factory = factory
    assert client.post(BASE + 'a/turns', json=retry).status_code == 200
    assert len(client.get(BASE + 'a/session').json()['items']) == 5
    # Existing records never return to the file writer after cutover.
    assert live_service.session('course', 'a', 'alice')['turns'] == []


def test_legacy_import_preserves_full_source_and_is_read_only(client, live_service):
    digest = hashlib.sha256(b'a').hexdigest()[:24]
    path = live_service.manager.get_classroom_qa_dir('course', 'learning_' + digest, 'alice') / 'session.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {'session_id': 'old-cqa-source', 'turns': [{'turn_id': str(i), 'question': f'q{i}', 'answer_text': f'a{i}'} for i in range(150)]}
    original = json.dumps(value).encode()
    path.write_bytes(original)
    result = client.post(BASE + 'a/enter').json()
    assert result['message_count'] == 301
    assert result['import_metadata']['legacy_session_id'] == 'old-cqa-source'
    assert client.post(BASE + 'a/enter').json()['message_count'] == 301
    assert path.read_bytes() == original


def test_reauthorization_rejects_persisted_history(client, live_service):
    client.post(BASE + 'a/enter')
    original = live_service.require
    def denied(course, owner):
        from fastapi import HTTPException
        raise HTTPException(404, 'no access')
    live_service.require = denied
    assert client.get(BASE + 'a/session').status_code == 404
    live_service.require = original
