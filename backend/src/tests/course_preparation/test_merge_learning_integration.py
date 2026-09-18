"""The retained tutoring implementation consumes committed preparation output."""
import pytest
from sqlalchemy.orm import Session
from app.database import Base
from app.chat.memory.lifecycle import MemoryLifecycle, MemoryChanged
from app.self_learning.prepared_courses import PreparedCourses
from app.self_learning.progress_repository import ProgressRepository, TABLES as PROGRESS_TABLES
from app.self_learning.progress_service import for_learning_service
from app.self_learning.postgres_repository import SessionRepository
from app.self_learning.session_service import SessionService
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.contracts import Actor
from tests.course_preparation.test_delivery import ready
from tests.course_preparation.test_generation_adapter import generation
from tests.test_self_learning import service
from tests.self_learning.test_memory_lifecycle import memory, agent_service, live_service, repository


def test_committed_course_opens_in_retained_learning_runtime(ready, service):
    repo, context, delivery = ready
    course = delivery.commit(context).result_ref['course_id']
    Base.metadata.create_all(repo.engine, tables=[Base.metadata.tables[n] for n in (
        'conversations', 'conversation_messages', 'learning_topic_sessions', 'learning_agent_turns', *PROGRESS_TABLES)])
    service.prepared_courses = PreparedCourses(repo.engine)
    service.session_repository = SessionRepository(repo.engine)
    service.sessions = SessionService(service, service.session_repository)
    service.progress_repository = ProgressRepository(repo.engine)
    service.progress_service = for_learning_service(service, service.progress_repository)
    room = service.room(course, 'alice')
    assert room['manifestRef']['version'] == 1
    assert room['chapters'][0]['id'] == 'tools'
    ref = room['chapters'][0]['resources'][0]['remote']
    assert ref['version'] == 1 and ref['materialType'] == 'report'
    assert any(r['id'] == course for r in service.overview('alice')['rooms'])
    view = service.progress_service.reader.read(Actor(user_id='alice'), course)
    assert view.source == 'manifest' and view.topics[0].completion_policy == 'explicit'
    entered = service.sessions.enter('alice', course, 'tools')
    assert entered['session_id']
    _, material = ContextBuilder(service).authorize('alice', course, 'tools', {'resource_ref': {
        'course_id': course, 'material_type': ref['materialType'], 'material_id': ref['materialId'], 'version': 1}})
    assert material['version'] == 1
    # The retained P5 producer can supplement a course that exists only in the
    # preparation manifest, with optional progress and no route replacement.
    from uuid import uuid4
    from app.course_preparation.production_models import TABLES
    from app.course_preparation.production_service import ProductionService, digest
    from app.course_preparation.schemas import PreparationRequest
    from app.self_learning.preparation_adapter import PreparationAdapter
    from tests.self_learning.test_preparation_adapter import producer
    Base.metadata.create_all(repo.engine, tables=[Base.metadata.tables[n] for n in TABLES])
    production = ProductionService(service, repo.engine, model_json=producer)
    service.preparations = PreparationAdapter(service, production)
    request = PreparationRequest(request_id=uuid4(), operation='supplement_node', goal='保存工具调用的补充解释',
        target={'course_id': course, 'node_id': 'tools', 'base_manifest_version': production.baseline('alice', course)},
        overrides={'required_resource_types': ['report']})
    receipt = production.accept('alice', request, 'merge-supplement',
        {'ref': {'course_id': course, 'material_type': 'report', 'material_id': ref['materialId'], 'version': 1},
         'hash': digest(material), 'text': material['content']}, {}, intent_hash='merge')
    from app.course_preparation.service import PreparationService
    from app.course_preparation.contracts import PreparationNotFound
    assert [r['preparation_id'] for r in PreparationService(repo).list('alice')] == [context.preparation_id]
    for action in (lambda: repo.get_public('alice', receipt['preparation_id']),
                   lambda: repo.cancel('alice', receipt['preparation_id']),
                   lambda: repo.retry('alice', receipt['preparation_id']),
                   lambda: repo.events(owner_user_id='alice', preparation_id=receipt['preparation_id'])):
        with pytest.raises(PreparationNotFound): action()
    assert production.get('alice', receipt['preparation_id'])['status'] == 'accepted'
    assert production.run_once()
    completed = production.get('alice', receipt['preparation_id'])
    assert completed['status'] == 'succeeded', completed
    extra = completed['result']['resource_refs'][0]
    room = service.room(course, 'alice')
    assert any(r['id'] == extra['material_id'] for r in room['chapters'][0]['resources'])
    view = service.progress_service.reader.read(Actor(user_id='alice'), course)
    added = next(r for r in view.topics[0].resources if r.resource_ref.material_id == extra['material_id'])
    assert added.required is False and view.manifest_ref.version == 1


def test_learning_preference_change_invalidates_preparation_context(memory):
    names = ('agent_memory_epochs', 'agent_memory_suppressions', 'agent_memory_dependencies', 'agent_memory_changes')
    Base.metadata.create_all(memory.engine, tables=[Base.metadata.tables[n] for n in names])
    memory.update('alice', 'course', 'example_order', 'course', '先举例', 0,
                  operation_id='first', explicit=True)
    lifecycle = MemoryLifecycle(memory.engine)
    view = lifecycle.read_effective('alice', course_id='course')
    preference = view['preferences']['learning_style']
    assert preference['value'] == '先举例'
    lifecycle.register_dependencies('alice', 'preparation:merge-test',
        {preference['memory_id']: preference['revision']}, expected_epoch=view['memory_epoch'])
    memory.delete('alice', 'course', 'example_order', 'course', 1, operation_id='delete')
    with pytest.raises(MemoryChanged):
        lifecycle.validate_consumer('alice', 'preparation:merge-test')
    assert not lifecycle.read_effective('alice', course_id='course')['preferences']
