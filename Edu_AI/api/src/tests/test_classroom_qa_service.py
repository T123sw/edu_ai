from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.integrations.openmaic import OpenMaicUnavailable
from app.schemas.classroom_qa import ClassroomQaTurnRequest
from app.services.classroom_qa_service import ClassroomQaError, ClassroomQaService
from app.services.classroom_qa_store import ClassroomQaSessionStore
from app.services.classroom_qa_tts import ClassroomQaTtsService
from core.course_storage import CourseStorageManager


pytestmark = pytest.mark.anyio


def classroom_material() -> dict:
    return {
        'title': '算法课堂',
        'scenes': [
            {
                'id': 'scene-1',
                'title': '快速排序',
                'actions': [
                    {'id': 'speech-1', 'type': 'speech', 'text': '先选择一个基准值。'},
                    {'id': 'speech-2', 'type': 'speech', 'text': '再把数据分到两侧。'},
                ],
            }
        ],
    }


def turn_request(*, client_turn_id=None, action_id='speech-1'):
    return ClassroomQaTurnRequest(
        client_turn_id=client_turn_id or uuid4(),
        question='为什么需要基准值？',
        checkpoint={
            'scene_id': 'scene-1',
            'scene_index': 0,
            'action_index': 0,
            'action_id': action_id,
            'phase': 'executing_action',
            'page_revision': 1,
        },
    )


class FakeGateway:
    def __init__(self):
        self.calls = 0
        self.error: Exception | None = None
        self.messages = None

    def chat(self, messages, temperature=0.2, max_tokens=1200):
        self.calls += 1
        self.messages = messages
        if self.error:
            raise self.error
        return json.dumps(
            {
                'answer_text': '基准值帮助我们把问题分成更小的部分。',
                'transition_text': '好，继续看数据如何被划分。',
            },
            ensure_ascii=False,
        )


class FakeTts:
    def __init__(self):
        self.calls = 0
        self.error: Exception | None = None

    async def synthesize_and_store(self, *, session_dir, turn_id, text):
        self.calls += 1
        if self.error:
            raise self.error
        return f'{turn_id}.mp3', 'audio/mpeg'


def create_service(tmp_path, *, material=None, rag_search=None):
    manager = CourseStorageManager(root_path=str(tmp_path))
    store = ClassroomQaSessionStore(manager)
    gateway = FakeGateway()
    tts = FakeTts()
    metrics = []
    selected_material = classroom_material() if material is None else material
    service = ClassroomQaService(
        store=store,
        material_loader=lambda **kwargs: selected_material,
        rag_search=rag_search or (lambda **kwargs: '课程知识库摘要'),
        gateway=gateway,
        tts=tts,
        metrics_sink=metrics.append,
    )
    return service, store, gateway, tts, metrics


async def test_submit_turn_is_idempotent_across_repeated_client_turn_id(tmp_path):
    service, _, gateway, tts, _ = create_service(tmp_path)
    request = turn_request()
    request_args = {
        'course_id': 'course-1',
        'classroom_id': 'classroom-1',
        'owner_user_id': 'student-a',
        'request': request,
    }

    first = await service.submit_turn(**request_args)
    second = await service.submit_turn(**request_args)

    assert first == second
    assert gateway.calls == 1
    assert tts.calls == 1
    assert first['turn']['tts_status'] == 'ready'
    assert first['turn']['audio_url'].endswith('.mp3')


async def test_tts_failure_preserves_answer_and_marks_degraded(tmp_path):
    service, _, _, tts, _ = create_service(tmp_path)
    tts.error = OpenMaicUnavailable('offline')

    result = await service.submit_turn(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
        request=turn_request(),
    )

    assert result['turn']['answer_text']
    assert result['turn']['tts_status'] == 'failed'
    assert result['turn']['audio_url'] is None


async def test_rag_failure_degrades_without_blocking_answer(tmp_path):
    def failing_rag(**kwargs):
        raise RuntimeError('rag offline')

    service, _, gateway, _, metrics = create_service(
        tmp_path,
        rag_search=failing_rag,
    )

    result = await service.submit_turn(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
        request=turn_request(),
    )

    assert result['turn']['answer_text']
    assert gateway.calls == 1
    assert metrics[-1]['rag_degraded'] is True


async def test_llm_failure_is_persisted_and_released_for_retry(tmp_path):
    service, store, gateway, _, _ = create_service(tmp_path)
    gateway.error = RuntimeError('llm offline')

    with pytest.raises(ClassroomQaError) as captured:
        await service.submit_turn(
            course_id='course-1',
            classroom_id='classroom-1',
            owner_user_id='student-a',
            request=turn_request(),
        )

    assert captured.value.code == 'CLASSROOM_QA_ANSWER_FAILED'
    assert captured.value.retryable is True
    session = store.load_or_empty(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    assert session['active_turn'] is None
    assert session['last_failure']['error_code'] == 'CLASSROOM_QA_ANSWER_FAILED'


async def test_stale_checkpoint_and_missing_material_have_stable_errors(tmp_path):
    service, _, gateway, _, _ = create_service(tmp_path)
    with pytest.raises(ClassroomQaError) as stale:
        await service.submit_turn(
            course_id='course-1',
            classroom_id='classroom-1',
            owner_user_id='student-a',
            request=turn_request(action_id='forged-action'),
        )
    assert stale.value.code == 'STALE_CLASSROOM_CHECKPOINT'
    assert stale.value.status_code == 409
    assert gateway.calls == 0

    missing, _, _, _, _ = create_service(tmp_path / 'missing', material=False)
    with pytest.raises(ClassroomQaError) as not_found:
        await missing.submit_turn(
            course_id='course-1',
            classroom_id='classroom-1',
            owner_user_id='student-a',
            request=turn_request(),
        )
    assert not_found.value.status_code == 404


async def test_busy_turn_maps_to_conflict_and_metrics_exclude_content(tmp_path):
    service, store, _, _, metrics = create_service(tmp_path)
    session = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    store.begin_turn(
        session=session,
        client_turn_id=str(uuid4()),
        question='占用中的问题',
        checkpoint=turn_request().checkpoint.model_dump(),
    )

    with pytest.raises(ClassroomQaError) as busy:
        await service.submit_turn(
            course_id='course-1',
            classroom_id='classroom-1',
            owner_user_id='student-a',
            request=turn_request(),
        )
    assert busy.value.code == 'CLASSROOM_QA_BUSY'
    assert busy.value.status_code == 409

    fresh, _, _, _, fresh_metrics = create_service(tmp_path / 'fresh')
    await fresh.submit_turn(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
        request=turn_request(),
    )
    metric = fresh_metrics[-1]
    assert {'rag_ms', 'llm_ms', 'tts_ms', 'total_ms'} <= metric.keys()
    rendered = json.dumps(metric, ensure_ascii=False)
    assert '为什么需要基准值' not in rendered
    assert '基准值帮助我们' not in rendered


class FakeOpenMaicClient:
    async def synthesize_tts(self, **kwargs):
        self.kwargs = kwargs
        return b'ID3-audio', 'mp3'


async def test_tts_service_atomically_persists_registered_audio(tmp_path):
    client = FakeOpenMaicClient()
    service = ClassroomQaTtsService(
        client=client,
        provider_id='qwen-tts',
        voice='Cherry',
        speed=1.0,
    )

    filename, mime_type = await service.synthesize_and_store(
        session_dir=Path(tmp_path),
        turn_id='turn-1',
        text='回答。\n回到课堂。',
    )

    assert filename == 'turn-1.mp3'
    assert mime_type == 'audio/mpeg'
    assert (Path(tmp_path) / 'audio' / filename).read_bytes() == b'ID3-audio'
    assert list((Path(tmp_path) / 'audio').glob('.*.tmp')) == []
