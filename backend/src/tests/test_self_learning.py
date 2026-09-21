import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.self_learning.service import LearningService
from app.self_learning.store import LearningStore
from app.services.course_membership_store import CourseMembershipStore
from core.course_storage import CourseStorageManager


@pytest.fixture
def service(tmp_path, monkeypatch):
    for key in ['APP_STATE', 'MATERIAL', 'KNOWLEDGE', 'COURSE', 'COURSE_MEMBERSHIP']:
        monkeypatch.setenv(key + '_PERSISTENCE_MODE', 'json')
    manager = CourseStorageManager(root_path=str(tmp_path / 'courses'))
    manager.create_course_structure('course')
    manager.save_course_info('course', {'id': 'course', 'title': 'Python', 'created_by': 'alice'})
    manager.save_knowledge_graph('course', {'root': {'id': 'root', 'children': [{'id': 'a', 'label': '变量'}, {'id': 'b', 'label': '条件'}]}})
    members = CourseMembershipStore(tmp_path / 'members.json')
    members.upsert('course', 'alice', 'owner', added_by='alice')
    members.upsert('course', 'bob', 'viewer', added_by='alice')
    class Model:
        calls = []
        def chat(self, messages, **kwargs):
            self.calls.append(messages)
            return '变量保存值。'
    model = Model()
    svc = LearningService(manager=manager, store=LearningStore(tmp_path), memberships=members, model_factory=lambda owner: model)
    svc.test_model = model
    return svc


def test_account_isolation_and_restart(service):
    service.patch('course', 'alice', {'progress': {'pending:a': {'position': 3, 'note': 'private'}}, 'understanding': {'a': 'review'}})
    restarted = LearningService(manager=service.manager, store=service.store, memberships=service.memberships)
    assert restarted.room('course', 'alice')['progress']['pending:a']['note'] == 'private'
    assert restarted.room('course', 'bob')['progress'] == {}
    with pytest.raises(HTTPException) as denied:
        service.room('course', 'outsider')
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        service.patch('course', 'alice', {'progress': {'outside': {'note': 'bad'}}})


def test_dialogue_chapter_isolation_global_memory_and_idempotency(service):
    service.patch('course', 'alice', {'understanding': {'b': 'review'}})
    request = str(uuid4())
    service.answer('course', 'alice', 'a', '变量是什么', request, 'pending:a')
    service.answer('course', 'alice', 'a', '变量是什么', request, 'pending:a')
    assert len(service.test_model.calls) == 1
    assert '条件' in service.test_model.calls[0][0]['content']
    assert 'review' in service.test_model.calls[0][0]['content']
    service.answer('course', 'alice', 'b', '条件是什么', str(uuid4()), 'pending:b')
    assert all('变量是什么' not in m['content'] for m in service.test_model.calls[1])
    assert service.room('course', 'bob')['messages'] == []
    assert len(service.room('course', 'alice')['messages']) == 4


def test_failure_releases_claim_and_keeps_history(service):
    class Broken:
        def chat(self, *args, **kwargs):
            raise RuntimeError('upstream unavailable')
    factory = service.model_factory
    service.model_factory = lambda owner: Broken()
    request = str(uuid4())
    with pytest.raises(HTTPException) as failed:
        service.answer('course', 'alice', 'a', 'test', request, 'pending:a')
    assert failed.value.status_code == 502
    service.model_factory = factory
    service.answer('course', 'alice', 'a', 'test', request, 'pending:a')
    assert len(service.room('course', 'alice')['messages']) == 2


def test_personal_copy_preserves_file_and_does_not_leak(service):
    service.manager.save_generated_material('course', 'report', 'report-one', {'title': '报告', 'final_markdown': '# 真正的内容', 'file_extension': '.md'}, file_data=b'# original', owner_user_id='alice')
    assert len(service.room('course', 'alice')['resources']) == 1
    assert service.room('course', 'bob')['resources'] == []
    room = service.attach('course', 'alice', 'a', 'report', 'report-one')
    copy_id = room['chapters'][0]['resources'][0]['id']
    service.attach('course', 'alice', 'a', 'report', 'report-one')
    assert len(service.room('course', 'alice')['chapters'][0]['resources']) == 1
    assert service.manager.delete_generated_material('course', 'report', 'report-one', owner_user_id='alice')
    copy = service.material('course', 'report', copy_id, 'alice')
    assert copy['final_markdown'] == '# 真正的内容'
    assert service.manager.get_file_path('course', copy['file_path']).read_bytes() == b'# original'
    assert service.room('course', 'alice')['resources'] == []
    assert service.room('course', 'bob')['chapters'][0]['resources'][0]['id'] == 'pending:a'


def test_pending_notes_survive_generated_content_replacing_placeholder(service):
    service.patch('course', 'alice', {'selectedId': 'pending:a', 'progress': {'pending:a': {'note': 'while generating'}}})
    service.manager.save_generated_material('course', 'report', 'lesson', {'title': '已生成', 'learning_course_resource': True}, owner_user_id='alice', scope_type='knowledge_point', scope_id='a')
    room = service.room('course', 'alice')
    assert room['selectedId'] == 'lesson'
    assert room['progress']['lesson']['note'] == 'while generating'
    service.patch('course', 'alice', {'progress': {'pending:a': {'note': 'late autosave'}}})
    assert service.room('course', 'alice')['progress']['lesson']['note'] == 'late autosave'


def test_practice_uses_server_answer_and_is_version_and_owner_bound(service):
    service.manager.save_generated_material('course', 'quiz', 'quiz', {'title': '变量', 'questions': [{'id': 'q1', 'stem': 'x=1', 'options': ['赋值', '比较'], 'answer': 'A'}]}, owner_user_id='alice')
    result = service.practice('course', 'alice', 'quiz', 1, {'q1': 'A'})
    assert result['correct'] == result['graded'] == 1
    assert service.room('course', 'alice')['practice']['quiz']['answers'] == {'q1': 'A'}
    assert service.room('course', 'bob')['practice'] == {}
    with pytest.raises(HTTPException):
        service.practice('course', 'bob', 'quiz', 1, {'q1': 'A'})
    with pytest.raises(HTTPException) as stale:
        service.practice('course', 'alice', 'quiz', 2, {'q1': 'A'})
    assert stale.value.status_code == 409


@pytest.mark.parametrize('duration,minutes,basis', [
    ({'basis':'estimated','value_minutes':1.9},1.9,'estimated'),
    ({'basis':'measured','value_minutes':2.4},2.4,'measured'),
    ({'basis':'unknown','value_minutes':None},0,'unknown'),
])
def test_prepared_resource_card_uses_its_own_duration(duration,minutes,basis):
    from app.self_learning.service import LearningService
    card=LearningService.resource(None, {'material_type':'report','material_id':'r','version':2,
        'generation_state':{'preparation':{'duration':duration}}})
    assert card['minutes']==minutes
    assert card['minutesBasis']==basis
