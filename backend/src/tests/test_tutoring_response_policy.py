"""Presentation rules reach model inputs without removing teaching evidence."""
import asyncio
import hashlib
import json

import pytest

from app.services.tutoring_response_policy import TUTORING_RESPONSE_POLICY


@pytest.mark.parametrize('kind', ['report', 'quiz', 'classroom'])
def test_learning_modes_version_the_shared_policy(kind, monkeypatch):
    from app.self_learning import teaching_skills

    original = teaching_skills.load_teaching_skill(kind)
    assert TUTORING_RESPONSE_POLICY in original['instructions']
    monkeypatch.setattr(teaching_skills, 'TUTORING_RESPONSE_POLICY', '更新后的回复规则')
    updated = teaching_skills.load_teaching_skill(kind)
    assert updated['version'] != original['version']
    assert updated['mode'] == original['mode']


def test_classroom_keeps_playback_evidence_out_of_fallback_transition():
    from app.services.classroom_qa_prompt import (
        build_classroom_qa_context, build_classroom_qa_messages, parse_classroom_qa_answer,
    )
    from tests.hyperframes.test_context_serving import lesson

    context = build_classroom_qa_context(
        material={'content': lesson()},
        checkpoint={'kind': 'hyperframes', 'seconds': 8}, recent_turns=[],
    )
    messages = build_classroom_qa_messages(question='为什么这样计算？', context=context)
    assert TUTORING_RESPONSE_POLICY in messages[0]['content']
    assert json.loads(context.scene_speech[0])['seconds'] == 8
    assert '讲稿b' in messages[1]['content']
    assert context.scene_title == 'b'
    _, transition = parse_classroom_qa_answer('计算结果是 8 秒。', scene_title=context.scene_title)
    assert '8秒' not in transition and '@' not in transition


@pytest.mark.parametrize('kind,include_answers', [('study_guide', True), ('practice', False)])
def test_resource_policy_keeps_answer_disclosure_contract(kind, include_answers):
    from app.services.resource_qa_prompt import ResourceQaContext, build_resource_qa_messages

    messages = build_resource_qa_messages(
        question='请解释', context=ResourceQaContext(kind, '资料', (), include_answers),
    )
    assert TUTORING_RESPONSE_POLICY in messages[0]['content']
    assert '只输出 JSON' in messages[0]['content']
    if not include_answers:
        assert '禁止猜测或泄露答案' in messages[0]['content']


def test_pbl_passes_policy_and_code_to_model(monkeypatch):
    from app.pbl.tutor import answer_question
    from app.practice import service

    context = {'question': '哪里有错？', 'files': {'/src/main.js': 'return 1'}, 'matchingRun': None}

    async def complete(owner, prompt, *, system, tokens):
        assert TUTORING_RESPONSE_POLICY in system
        assert json.loads(prompt) == context
        return '先检查返回值。'

    monkeypatch.setattr(service, 'complete', complete)
    assert asyncio.run(answer_question('alice', context)) == '先检查返回值。'


def test_experiment_freezes_policy_and_delivers_it_to_stream(tmp_path, monkeypatch):
    from app.practice.service import PracticeStore
    from app.practice.experiment.repository import ExperimentRepository
    from app.practice.experiment.tutor import TutorRepository, stream_turn
    from tests.practice.test_experiment_tutor import FakeModel, package, question

    monkeypatch.setenv('APP_STATE_PERSISTENCE_MODE', 'json')
    repo = TutorRepository(ExperimentRepository(PracticeStore(root=tmp_path)))
    row, _ = repo.prepare('alice', 'lab', package(), question())
    assert TUTORING_RESPONSE_POLICY in row['skill']
    assert row['skill_version'] == hashlib.sha256(row['skill'].encode()).hexdigest()
    model = FakeModel()

    async def consume():
        return [event async for event in stream_turn(repo, 'alice', 'lab', row, True, model=model)]

    asyncio.run(consume())
    assert model.rounds[0][0]['content'] == row['skill']
    assert repo.get('alice', 'lab', row['request_id'])['status'] == 'complete'


def test_exam_passes_policy_without_changing_answer_or_citations():
    from app.exam_practice.worker import PracticeWorker

    class Worker(PracticeWorker):
        def __init__(self):
            pass

        async def complete(self, owner, messages, tools, deadline, context):
            assert TUTORING_RESPONSE_POLICY in messages[0]['content']
            assert json.loads(messages[1]['content'])['context']['question']['stem'] == '1+1？'
            return {'content': '{"answer":"先从加法的含义想起。"}', 'calls': []}

    turn = {'context': {'question': {'stem': '1+1？'}}, 'question': '给个提示',
            'question_id': 'q1', 'question_number': '1'}
    answer, citations = asyncio.run(Worker().chat('alice', turn, {}, {}, [], None))
    assert answer == '先从加法的含义想起。'
    assert citations == [{'question_id': 'q1', 'label': '第 1 题'}]


@pytest.mark.parametrize('role', ['teacher', 'student'])
def test_legacy_chat_personas_share_presentation_boundary(role):
    from app.chat.domain.persona_policy import persona_for

    assert TUTORING_RESPONSE_POLICY in persona_for(role).system_instruction()
