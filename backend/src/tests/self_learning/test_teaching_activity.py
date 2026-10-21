import asyncio
import importlib.util
import json
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, inspect
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.database import Base
from app.self_learning.check_service import CheckSubmission
from app.self_learning.context_builder import ContextBuilder
from app.self_learning.teaching_activity import TeachingActivityService
from app.self_learning.teaching_activity_models import TABLES, LearningTeachingFeedback as Feedback
from app.self_learning.turn_contracts import AnswerRequest
from app.self_learning.agent_runtime import LearningAgentRuntime
from tests.self_learning.test_checks import checks, offer, submit
from tests.self_learning.test_agent_runtime import agent_service, Model
from tests.self_learning.test_session_api import live_service, repository


@pytest.fixture
def coaching(checks):
    Base.metadata.create_all(checks.engine, tables=[Base.metadata.tables[n] for n in TABLES])
    checks.teaching = TeachingActivityService(checks)
    return checks


def request(check, attempt=None, draft=None, index=0):
    practice = {'check_id': check['check_id']}
    if attempt:
        practice['attempt_id'] = attempt['attempt_id']
    if draft is not None:
        practice['draft'] = draft
    return AnswerRequest(request_id=uuid4(), question='解释我的答案', reading_context={
        'resource_ref': check['source_ref'], 'locator': {'kind': 'quiz', 'question_index': index}, 'practice': practice})


def test_actual_attempt_and_draft_are_distinct_and_scoped(coaching):
    check = offer(coaching)
    wrong = submit(coaching, check, option_ids=['option_2'])
    svc = coaching.learning
    req = request(check, wrong)
    turn = svc.turns.accept('alice', 'course', 'a', req)
    packet = ContextBuilder(svc).build(svc.turn_repository.get('alice', turn['turn_id']))
    data = json.loads(packet['messages'][-3]['content'].split('\n', 1)[1])['practice']
    assert data['attempt']['option_ids'] == ['option_2'] and data['attempt']['correct'] is False
    assert data['answer_status'] == 'submitted'
    draft = request(check, draft={'option_ids': ['option_1'], 'text': ''}).reading_context.model_dump()
    value = coaching.teaching.resolve('alice', 'course', 'a', draft)
    assert value['answer_status'] == 'unsubmitted_draft' and 'attempt' not in value
    assert len(coaching.get('alice', check['check_id'])['attempts']) == 1
    for owner, topic in [('bob', 'a'), ('alice', 'b')]:
        with pytest.raises(HTTPException):
            coaching.teaching.resolve(owner, 'course', topic, req.reading_context.model_dump())
    draft['practice']['draft']['option_ids'] = ['foreign-option']
    with pytest.raises(HTTPException):
        coaching.teaching.resolve('alice', 'course', 'a', draft)


def test_check_attempt_and_position_cannot_be_substituted(coaching):
    first, second = offer(coaching), offer(coaching)
    attempt = submit(coaching, second, option_ids=['option_1'])
    with pytest.raises(HTTPException):
        coaching.teaching.resolve('alice', 'course', 'a', request(first, attempt).reading_context.model_dump())
    with pytest.raises(HTTPException):
        coaching.teaching.resolve('alice', 'course', 'a', request(first, index=1).reading_context.model_dump())
    ref = request(first).reading_context.model_dump()
    ref['resource_ref']['version'] = 2
    with pytest.raises(HTTPException):
        coaching.teaching.resolve('alice', 'course', 'a', ref)


def test_coaching_survives_restart_and_feedback_is_exactly_once(coaching):
    check = offer(coaching)
    configured = coaching.teaching.configure('alice', check['check_id'], True, 0)
    assert configured['revision'] == 1
    assert coaching.teaching.configure('alice', check['check_id'], True, 0) == configured
    assert TeachingActivityService(coaching).view('alice', check['check_id']) == configured
    req = CheckSubmission(request_id=uuid4(), question_version=1, option_ids=['option_2'])
    attempt = asyncio.run(coaching.submit('alice', check['check_id'], req))
    assert asyncio.run(coaching.submit('alice', check['check_id'], req)) == attempt
    svc, model = coaching.learning, Model()
    coaching.teaching.enqueue_pending()
    with Session(coaching.engine) as db:
        event = db.get(Feedback, attempt['attempt_id'])
        original_turn = event.turn_id
        # Simulate a crash after turn acceptance but before its outbox receipt.
        event.status, event.turn_id = 'pending', None
        db.commit()
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: model)
    assert runtime.run_once()
    assert not runtime.run_once()
    state = coaching.teaching.view('alice', check['check_id'])
    assert state['feedback']['turn_id'] == original_turn and state['feedback']['status'] == 'succeeded'
    assert 'option_2' in model.messages[0] and '"answer_status": "submitted"' in model.messages[0].replace('\\"', '"')
    with Session(coaching.engine) as db:
        assert len(list(db.scalars(select(Feedback)))) == 1
    assert len(svc.turn_repository.list_topic('alice', svc.sessions.enter('alice', 'course', 'a')['session_id'])) == 1


def test_ordinary_skipped_and_disabled_checks_do_not_start_conversations(coaching):
    check = offer(coaching)
    submit(coaching, check, option_ids=['option_1'])
    coaching.teaching.configure('alice', check['check_id'], True, 0)
    submit(coaching, check, skipped=True)
    coaching.teaching.configure('alice', check['check_id'], False, 1)
    with pytest.raises(HTTPException):
        coaching.teaching.configure('alice', check['check_id'], True, 0)
    submit(coaching, check, option_ids=['option_2'])
    with Session(coaching.engine) as db:
        assert list(db.scalars(select(Feedback))) == []


def test_feedback_waits_for_user_turn_without_losing_attempt(coaching):
    check = offer(coaching)
    svc = coaching.learning
    manual = svc.turns.accept('alice', 'course', 'a', request(check))
    coaching.teaching.configure('alice', check['check_id'], True, 0)
    attempt = submit(coaching, check, option_ids=['option_2'])
    coaching.teaching.enqueue_pending()
    assert coaching.teaching.view('alice', check['check_id'])['feedback']['status'] == 'pending'
    runtime = LearningAgentRuntime(svc, svc.turn_repository, lambda _: Model())
    assert runtime.run_once() and runtime.run_once()
    assert svc.turns.get('alice', manual['turn_id'])['status'] == 'succeeded'
    assert coaching.teaching.view('alice', check['check_id'])['feedback']['attempt_id'] == attempt['attempt_id']


def test_subjective_evaluation_failure_then_retry_continues_once(coaching):
    coaching.learning.manager.save_generated_material('course', 'report', 'b-doc',
        {'title': '赋值说明', 'content': '赋值将值绑定到变量名字。'}, owner_user_id='alice',
        visibility='course', scope_type='knowledge_point', scope_id='b')
    async def generator(_):
        return {'form': 'short_answer', 'stem': '解释赋值', 'reference_answer': '绑定值'}
    async def broken(_):
        raise RuntimeError('unavailable')
    async def evaluator(_):
        return {'supported': True, 'feedback': '本次回答体现了绑定关系'}
    coaching.generator, coaching.evaluator = generator, broken
    check = asyncio.run(coaching.offer('alice', 'course', 'b', str(uuid4()), preferred_form='short_answer'))
    coaching.teaching.configure('alice', check['check_id'], True, 0)
    attempt = submit(coaching, check, text='将值绑定到名字')
    assert attempt['status'] == 'evaluation_failed'
    assert coaching.teaching.view('alice', check['check_id'])['feedback'] is None
    coaching.evaluator = evaluator
    for _ in range(2):
        asyncio.run(coaching.evaluate('alice', check['check_id'], attempt['attempt_id']))
    assert coaching.teaching.view('alice', check['check_id'])['feedback']['status'] == 'pending'


def test_material_mapping_and_old_mapping_are_version_bound(coaching):
    items = coaching.material_checks('alice', 'course', 'quiz1', 1)['items']
    check = items[0]
    assert check['source_locator'] == {'kind': 'quiz', 'question_index': 0}
    assert coaching.teaching.resolve('alice', 'course', 'a', request(check).reading_context.model_dump())['check_id'] == check['check_id']
    from app.self_learning.enrichment_models import LearningCheck
    with Session(coaching.engine) as db:
        row = db.get(LearningCheck, check['check_id'])
        row.source = {k: v for k, v in row.source.items() if k != 'question_index'}
        db.commit()
    assert coaching.teaching.resolve('alice', 'course', 'a', request(check).reading_context.model_dump())
    assert coaching.material_checks('alice', 'course', 'quiz1', 1)['items'][0]['check_id'] == check['check_id']


def test_unavailable_source_fails_feedback_without_losing_saved_answer(coaching):
    check = offer(coaching)
    coaching.teaching.configure('alice', check['check_id'], True, 0)
    saved = submit(coaching, check, option_ids=['option_2'])
    coaching.learning.manager.save_generated_material('course', 'quiz', 'quiz1', {
        'title': '替换版本', 'questions': [{'stem': '另一题', 'options': ['是', '否'], 'answer': 'A'}]},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    coaching.teaching.enqueue_pending()
    state = coaching.teaching.view('alice', check['check_id'])
    assert state['feedback']['status'] == 'failed'
    assert coaching.get('alice', check['check_id'])['attempts'][0]['attempt_id'] == saved['attempt_id']


def test_new_tables_migration_round_trip(checks):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20261013_0037_teaching_activities.py'
    spec = importlib.util.spec_from_file_location('teaching_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with checks.engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        for name in TABLES:
            assert {c['name'] for c in inspect(conn).get_columns(name)} == set(Base.metadata.tables[name].columns.keys())
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        assert not set(TABLES) & set(inspect(conn).get_table_names())


def test_long_question_draft_and_current_question_fit_budget(coaching):
    from app.self_learning.tools import LearningTools
    svc = coaching.learning
    stem, answer, question = '请解释变量关系。' * 333, '赋值关系' * 1000, '解释' * 1000
    svc.manager.save_generated_material('course', 'quiz', 'long-check', {
        'title': '长简答题', 'questions': [{'stem': stem, 'answer': '赋值绑定变量与值。'}]},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    check = coaching.material_checks('alice', 'course', 'long-check', 1)['items'][0]
    req = request(check, draft={'text': answer, 'option_ids': []})
    req.question = question
    req.reading_context.selected_text = stem
    accepted = svc.turns.accept('alice', 'course', 'a', req)
    turn = svc.turn_repository.get('alice', accepted['turn_id'])
    schemas = LearningTools(svc, turn, {}).schemas()
    budget = 64000 - len(json.dumps(schemas, ensure_ascii=False).encode()) - 8000
    packet = ContextBuilder(svc).build(turn, budget=budget)
    data = json.loads(packet['messages'][-3]['content'].split('\n', 1)[1])
    assert data['selected_text'] == stem and data['selection_verified']
    assert data['practice']['draft']['text'] == answer
    assert packet['messages'][-1]['content'] == question
    assert len(json.dumps(packet['messages'], ensure_ascii=False).encode()) <= budget


def test_material_checks_authorize_once_and_preserve_attempts_and_coaching(coaching, monkeypatch):
    svc = coaching.learning
    svc.manager.save_generated_material('course', 'quiz', 'batch', {
        'title': '多题练习', 'learning_course_resource': True,
        'questions': [{'id': str(i), 'type': 'single_choice', 'stem': f'题目 {i}',
                       'options': ['正确选项', '另一选项'], 'answer': 'A'} for i in range(10)]},
        owner_user_id='alice', visibility='course', scope_type='knowledge_point', scope_id='a')
    counts = {'room': 0, 'material': 0}
    for name in counts:
        original = getattr(svc, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            counts[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(svc, name, counted)
    batch = coaching.material_checks('alice', 'course', 'batch', 1)
    assert len(batch['items']) == 10
    assert counts == {'room': 1, 'material': 1}
    check = batch['items'][0]
    coaching.teaching.configure('alice', check['check_id'], True, 0)
    attempt = submit(coaching, check, option_ids=['option_1'])
    counts.update(room=0, material=0)
    restored = coaching.material_checks('alice', 'course', 'batch', 1)
    assert counts == {'room': 1, 'material': 1}
    first = restored['items'][0]
    assert first['attempts'][0]['attempt_id'] == attempt['attempt_id']
    assert first['teaching']['enabled'] is True
    assert first['teaching']['latest_attempt_id'] == attempt['attempt_id']
    assert all(not item['attempts'] for item in restored['items'][1:])
    assert 'correct_option_ids' not in first['public_question']
    with pytest.raises(HTTPException):
        coaching.material_checks('outsider', 'course', 'batch', 1)


def test_single_check_reuses_authorization_for_teaching_view(coaching, monkeypatch):
    check = offer(coaching)
    original = coaching.topic
    calls = []
    def topic(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(coaching, 'topic', topic)
    result = coaching.get('alice', check['check_id'])
    assert len(calls) == 1
    assert result['teaching']['check_id'] == check['check_id']
