from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.course_preparation.runtime_contracts import BudgetCost, BudgetLimits, ExecutionContext, ToolCall, ToolSpec
from app.course_preparation.tool_registry import ToolRegistry
from app.course_preparation.tool_dispatcher import ToolDispatcher
from app.course_preparation.lifecycle_repository import LifecycleRepository, StaleLease, BudgetExceeded
from app.course_preparation.schemas import Contract, PreparationRequest


class Args(Contract):
    value: int


class Allow:
    def authorize(self, owner_user_id, request):
        if owner_user_id != 'alice':
            raise PermissionError('denied')


def request():
    return PreparationRequest(request_id=uuid4(), operation='create_course', goal='学习 Agent 开发准备面试')


def repo(engine, now=None):
    return LifecycleRepository(engine, authorizer=Allow(), clock=(lambda: now[0]) if now else None)


def test_lifecycle_cancel_retry_and_old_worker_fence(runtime_engine):
    service = repo(runtime_engine)
    accepted = service.submit('alice', request())
    claim = service.claim('worker-1')
    service.cancel('alice', accepted['preparation_id'], expected_revision=claim.revision)
    with pytest.raises(StaleLease):
        service.checkpoint(claim, {'bad': True})
    retried = service.retry('alice', claim.preparation_id)
    assert retried['attempt_no'] == 2
    newer = service.claim('worker-2')
    assert newer.attempt_no == 2
    with pytest.raises(StaleLease):
        service.checkpoint(claim, {})
    assert service.events(owner_user_id='alice', preparation_id=claim.preparation_id)[-1].attempt_no == 2


def test_reclaim_preserves_checkpoint_and_shared_budget(runtime_engine):
    now = [datetime.now(timezone.utc)]
    service = repo(runtime_engine, now)
    value = service.submit('alice', request(), limits=BudgetLimits(calls=2, tokens=100, cost_micro_usd=100, seconds=600))
    old = service.claim('old')
    action = service.begin_action(old, 'model1', 'model', {'query': 'x'}, BudgetCost(calls=1, tokens=50, cost_micro_usd=40))
    service.finish_action(old, action['action_id'], {'ok': True}, BudgetCost(calls=1, tokens=30, cost_micro_usd=20))
    service.checkpoint(old, {'source': 'persistent'})
    now[0] += timedelta(seconds=151)
    new = service.claim('new')
    assert new.checkpoint == {'source': 'persistent'}
    with pytest.raises(StaleLease):
        service.checkpoint(old, {})
    service.begin_action(new, 'model2', 'model', {}, BudgetCost(calls=1, tokens=70, cost_micro_usd=80))
    with pytest.raises(BudgetExceeded):
        service.begin_action(new, 'model3', 'model', {}, BudgetCost(calls=1))
    assert service.get_public('alice', value['preparation_id'])['budget']['consumed']['tokens'] == 30


def test_pending_action_identity_survives_crash_and_payload_conflicts(runtime_engine):
    now = [datetime.now(timezone.utc)]
    service = repo(runtime_engine, now)
    service.submit('alice', request())
    old = service.claim('old')
    first = service.begin_action(old, 'generate-node-1-v1', 'generate', {'node': 1}, BudgetCost(calls=1))
    now[0] += timedelta(seconds=151)
    new = service.claim('new')
    replay = service.begin_action(new, 'generate-node-1-v1', 'generate', {'node': 1}, BudgetCost(calls=1))
    assert replay['action_id'] == first['action_id'] and replay['status'] == 'pending'
    with pytest.raises(ValueError):
        service.begin_action(new, 'generate-node-1-v1', 'generate', {'node': 2}, BudgetCost(calls=1))


def test_registry_freezes_scope_policy_capabilities_and_digest():
    called = []
    specs = [ToolSpec('search', Args, lambda *a: called.append(a), stages=('research_scope',), network=True),
             ToolSpec('write', Args, lambda *a: None, stages=('produce',), readonly=False, capability='generate')]
    registry = ToolRegistry(specs)
    ctx = ExecutionContext(preparation_id='p', attempt_no=1, owner_user_id='alice', lease_token='x',
                           revision=1, stage='research_scope', operation='create_course', source_policy='uploaded_only')
    assert not registry.mount(ctx).tools
    allowed = registry.mount(ctx.model_copy(update={'source_policy': 'open'}))
    assert len(allowed.tools) == 1 and allowed.digest == registry.mount(ctx.model_copy(update={'source_policy': 'open'})).digest
    assert allowed.digest != registry.mount(ctx).digest


def test_batch_is_validated_before_any_effect(runtime_engine):
    service = repo(runtime_engine)
    service.submit('alice', request())
    claim = service.claim('worker')
    effects = []
    registry = ToolRegistry([ToolSpec('read', Args, lambda *args: effects.append('read')),
                             ToolSpec('write', Args, lambda *args: effects.append('write'), readonly=False)])
    dispatcher = ToolDispatcher(registry, service)
    with pytest.raises(ValueError):
        dispatcher.dispatch(claim, [ToolCall(call_id='1', name='read', arguments={'value': 1}),
                                    ToolCall(call_id='2', name='write', arguments={'value': 2})])
    with pytest.raises(ValueError):
        dispatcher.dispatch(claim, [ToolCall(call_id='1', name='read', arguments={'bad': 1})])
    assert effects == []
