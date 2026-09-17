from app.database import Base
from app.self_learning.progress_repository import ProgressRepository, TABLES
from app.self_learning.progress_service import for_learning_service
from tests.self_learning.test_session_api import live_service, client, repository
from tests.self_learning.test_progress_repository import event


def enable(svc):
    Base.metadata.create_all(svc.session_repository.engine, tables=[Base.metadata.tables[n] for n in TABLES])
    svc.progress_service = for_learning_service(svc, ProgressRepository(svc.session_repository.engine))
    svc.manager.save_generated_material('course', 'report', 'doc', {'title': 'Document', 'content': 'Hello', 'learning_course_resource': True},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')


def test_http_projection_replay_scope_and_old_write_guard(client, live_service):
    enable(live_service)
    url = '/api/self-learning/courses/course'
    e = event().model_dump(mode='json')
    first = client.post(url + '/topics/a/events', json=e)
    assert first.status_code == 200, first.text
    assert client.post(url + '/topics/a/events', json=e).json() == first.json()
    room = client.get(url).json()
    assert room['progress']['doc']['completed']
    assert room['learningProjection']['topics'][0]['judgment'] == 'unverified'
    assert room['learningProjection']['topics'][0]['progress'] == 'in_progress'  # no legacy requirement rules
    assert client.post(url + '/topics/b/events', json=e).status_code == 409
    assert client.post(url + '/topics/a/events', json=e, headers={'x-user': 'outsider'}).status_code == 404
    assert not client.get(url, headers={'x-user': 'bob'}).json()['progress']['doc']['completed']
    assert client.patch(url + '/learning', json={'progress': {'doc': {'completed': True}}}).status_code == 409
    assert client.patch(url + '/learning', json={'progress': {'doc': {'note': 'my note'}}}).status_code == 200
    assert client.get(url).json()['progress']['doc']['note'] == 'my note'
    assert client.get(url).json()['progress']['doc']['completed']
    e['resource_ref']['version'] = 2
    assert client.post(url + '/topics/a/events', json=e).status_code == 409
