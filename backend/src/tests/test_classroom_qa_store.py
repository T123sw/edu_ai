from __future__ import annotations

import os
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.classroom_qa import ClassroomQaTurnRequest
from app.services.classroom_qa_store import (
    ClassroomQaBusyError,
    ClassroomQaSessionStore,
)
from core.course_storage import CourseStorageManager


def checkpoint() -> dict:
    return {
        'scene_id': 'scene-1',
        'scene_index': 0,
        'action_index': 0,
        'action_id': 'speech-1',
        'phase': 'executing_action',
        'page_revision': 1,
    }


def make_store(tmp_path) -> tuple[ClassroomQaSessionStore, CourseStorageManager]:
    manager = CourseStorageManager(root_path=str(tmp_path))
    return ClassroomQaSessionStore(manager), manager


def test_turn_request_trims_question_and_rejects_blank_text():
    request = ClassroomQaTurnRequest(
        client_turn_id=uuid4(),
        question='  为什么？  ',
        checkpoint=checkpoint(),
    )
    assert request.question == '为什么？'

    with pytest.raises(ValidationError):
        ClassroomQaTurnRequest(
            client_turn_id=uuid4(),
            question='   ',
            checkpoint=checkpoint(),
        )


def test_empty_session_read_is_deterministic_and_does_not_write(tmp_path):
    store, manager = make_store(tmp_path)

    first = store.load_or_empty(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    second = store.load_or_empty(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )

    assert first == second
    assert first['session_id'].startswith('cqa_')
    assert first['turns'] == []
    assert not manager.get_classroom_qa_dir(
        'course-1', 'classroom-1', 'student-a'
    ).exists()


def test_get_or_create_is_idempotent_and_separates_owners(tmp_path):
    store, manager = make_store(tmp_path)

    student_a = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    again = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    student_b = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-b',
    )

    assert student_a == again
    assert student_a['session_id'] != student_b['session_id']
    assert manager.get_classroom_qa_dir(
        'course-1', 'classroom-1', 'student-a'
    ) != manager.get_classroom_qa_dir(
        'course-1', 'classroom-1', 'student-b'
    )


def test_different_unfinished_turn_is_rejected_until_completion(tmp_path):
    store, _ = make_store(tmp_path)
    session = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    first_id = str(uuid4())
    store.begin_turn(
        session=session,
        client_turn_id=first_id,
        question='第一个问题',
        checkpoint=checkpoint(),
    )

    with pytest.raises(ClassroomQaBusyError):
        store.begin_turn(
            session=session,
            client_turn_id=str(uuid4()),
            question='第二个问题',
            checkpoint=checkpoint(),
        )

    completed = {
        'turn_id': 'turn-1',
        'client_turn_id': first_id,
        'question': '第一个问题',
        'answer_text': '回答',
        'transition_text': '继续上课',
        'tts_status': 'failed',
        'audio_url': None,
        'created_at': '2026-08-10T00:00:00Z',
    }
    store.complete_turn(session=session, client_turn_id=first_id, turn=completed)
    store.begin_turn(
        session=session,
        client_turn_id=str(uuid4()),
        question='第二个问题',
        checkpoint=checkpoint(),
    )


def test_stale_claim_is_reclaimed_after_120_seconds(tmp_path):
    store, manager = make_store(tmp_path)
    session = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    store.begin_turn(
        session=session,
        client_turn_id=str(uuid4()),
        question='旧问题',
        checkpoint=checkpoint(),
    )
    claim = manager.get_classroom_qa_dir(
        'course-1', 'classroom-1', 'student-a'
    ) / 'active-turn.lock'
    os.utime(claim, (0, 0))

    active = store.begin_turn(
        session=session,
        client_turn_id=str(uuid4()),
        question='新问题',
        checkpoint=checkpoint(),
    )

    assert active['question'] == '新问题'


def test_completed_history_is_atomically_replaced_and_capped_at_100(tmp_path):
    store, manager = make_store(tmp_path)
    session = store.get_or_create(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )

    for index in range(101):
        client_turn_id = str(uuid4())
        store.begin_turn(
            session=session,
            client_turn_id=client_turn_id,
            question=f'问题 {index}',
            checkpoint=checkpoint(),
        )
        store.complete_turn(
            session=session,
            client_turn_id=client_turn_id,
            turn={
                'turn_id': f'turn-{index}',
                'client_turn_id': client_turn_id,
                'question': f'问题 {index}',
                'answer_text': f'回答 {index}',
                'transition_text': '继续',
                'tts_status': 'failed',
                'audio_url': None,
                'created_at': f'2026-08-10T00:{index // 60:02d}:{index % 60:02d}Z',
            },
        )

    loaded = store.load_or_empty(
        course_id='course-1',
        classroom_id='classroom-1',
        owner_user_id='student-a',
    )
    session_dir = manager.get_classroom_qa_dir(
        'course-1', 'classroom-1', 'student-a'
    )
    assert len(loaded['turns']) == 100
    assert loaded['turns'][0]['turn_id'] == 'turn-1'
    assert not (session_dir / 'active-turn.lock').exists()
    assert list(session_dir.glob('.*.tmp')) == []
