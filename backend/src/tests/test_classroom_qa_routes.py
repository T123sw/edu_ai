from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import course_dependencies
from app.api.classroom_qa import get_classroom_qa_service, router
from app.services.classroom_qa_service import ClassroomQaService
from app.services.classroom_qa_store import ClassroomQaSessionStore
from course_api_test_support import CourseApiTestFactory


class Gateway:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return json.dumps(
            {
                'answer_text': '基准值帮助划分数据。',
                'transition_text': '继续观察划分过程。',
            },
            ensure_ascii=False,
        )


class FileTts:
    async def synthesize_and_store(self, *, session_dir: Path, turn_id: str, text: str):
        audio_dir = session_dir / 'audio'
        audio_dir.mkdir(parents=True, exist_ok=True)
        filename = f'{turn_id}.mp3'
        (audio_dir / filename).write_bytes(b'ID3-route-audio')
        return filename, 'audio/mpeg'


class QaRouteHarness:
    def __init__(self, tmp_path, monkeypatch):
        self.course = CourseApiTestFactory(tmp_path, monkeypatch)
        self.course.users.append({'username': 'student-b', 'role': 'student'})
        self.course.memberships.upsert(
            'course-1', 'student-b', 'viewer', added_by='fixture'
        )
        self.course.manager.save_published_material_manifest(
            'course-1',
            'classroom',
            'classroom-1',
            {
                'title': '算法课堂',
                'scenes': [
                    {
                        'id': 'scene-1',
                        'title': '快速排序',
                        'actions': [
                            {
                                'id': 'speech-1',
                                'type': 'speech',
                                'text': '先选择一个基准值。',
                            }
                        ],
                    }
                ],
            },
        )
        self.gateway = Gateway()
        self.store = ClassroomQaSessionStore(self.course.manager)
        self.service = ClassroomQaService(
            store=self.store,
            storage=self.course.manager,
            gateway=self.gateway,
            tts=FileTts(),
        )

    def client(self, username='student-a', role='student') -> TestClient:
        app = FastAPI()
        app.include_router(router)
        identity = {'username': username, 'role': role}
        app.dependency_overrides[course_dependencies.get_current_user] = lambda: identity
        app.dependency_overrides[
            course_dependencies.get_course_access_service
        ] = lambda: self.course.access
        app.dependency_overrides[get_classroom_qa_service] = lambda: self.service
        return TestClient(app)

    def anonymous(self) -> TestClient:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[
            course_dependencies.get_course_access_service
        ] = lambda: self.course.access
        app.dependency_overrides[get_classroom_qa_service] = lambda: self.service
        return TestClient(app)


@pytest.fixture
def qa(tmp_path, monkeypatch):
    return QaRouteHarness(tmp_path, monkeypatch)


def turn_payload(*, client_turn_id=None, action_id='speech-1', question='为什么？'):
    return {
        'client_turn_id': str(client_turn_id or uuid4()),
        'question': question,
        'checkpoint': {
            'scene_id': 'scene-1',
            'scene_index': 0,
            'action_index': 0,
            'action_id': action_id,
            'phase': 'executing_action',
            'page_revision': 1,
        },
    }


def base_route():
    return '/api/courses/course-1/classrooms/classroom-1/qa'


def test_session_requires_auth_and_course_read(qa):
    assert qa.anonymous().get(f'{base_route()}/session').status_code == 401
    assert qa.client('outsider').get(f'{base_route()}/session').status_code == 403
    assert qa.client().get(f'{base_route()}/session').status_code == 200


def test_private_classroom_not_visible_to_another_student(qa):
    qa.course.manager.save_generated_material(
        'course-1',
        'classroom',
        'private-b',
        {'title': 'B 私有课堂', 'scenes': []},
        owner_user_id='student-b',
        visibility='private',
    )

    response = qa.client('student-a').get(
        '/api/courses/course-1/classrooms/private-b/qa/session'
    )

    assert response.status_code == 404


@pytest.mark.parametrize('question', ['   ', '问' * 1001])
def test_turn_validates_trimmed_question_bounds(qa, question):
    response = qa.client().post(
        f'{base_route()}/turns',
        json=turn_payload(question=question),
    )
    assert response.status_code == 422


def test_busy_and_stale_checkpoint_return_structured_conflicts(qa):
    session = qa.store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    qa.store.begin_turn(
        session=session,
        client_turn_id=str(uuid4()),
        question='占用',
        checkpoint=turn_payload()['checkpoint'],
    )
    busy = qa.client().post(f'{base_route()}/turns', json=turn_payload())
    assert busy.status_code == 409
    assert busy.json()['detail']['code'] == 'CLASSROOM_QA_BUSY'

    stale_qa = QaRouteHarness.__new__(QaRouteHarness)
    stale_qa.__dict__.update(qa.__dict__)
    stale_store = ClassroomQaSessionStore(
        type(qa.course.manager)(root_path=str(qa.course.manager.root_path / 'stale'))
    )
    stale_qa.store = stale_store
    stale_qa.service = ClassroomQaService(
        store=stale_store,
        storage=qa.course.manager,
        gateway=qa.gateway,
        tts=FileTts(),
    )
    stale = stale_qa.client().post(
        f'{base_route()}/turns',
        json=turn_payload(action_id='forged'),
    )
    assert stale.status_code == 409
    assert stale.json()['detail']['code'] == 'STALE_CLASSROOM_CHECKPOINT'


def test_duplicate_turn_is_idempotent_and_audio_is_owner_protected(qa):
    client_turn_id = uuid4()
    student_a = qa.client('student-a')
    first = student_a.post(
        f'{base_route()}/turns',
        json=turn_payload(client_turn_id=client_turn_id),
    )
    second = student_a.post(
        f'{base_route()}/turns',
        json=turn_payload(client_turn_id=client_turn_id),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert qa.gateway.calls == 1

    audio_url = first.json()['turn']['audio_url']
    own_audio = student_a.get(audio_url)
    other_audio = qa.client('student-b').get(audio_url)
    unknown = student_a.get(audio_url.rsplit('/', 1)[0] + '/unknown.mp3')
    traversal = student_a.get(audio_url.rsplit('/', 1)[0] + '/..%2Fsession.json')

    assert own_audio.status_code == 200
    assert own_audio.content == b'ID3-route-audio'
    assert own_audio.headers['content-type'].startswith('audio/mpeg')
    assert other_audio.status_code == 404
    assert unknown.status_code == 404
    assert traversal.status_code == 404
