from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.course_preparation.lifecycle_repository import BudgetExceeded, NoProgress, RevisionConflict, StaleLease
from app.course_preparation.runtime_contracts import BudgetCost, BudgetLimits, ToolCall, ToolSpec
from app.course_preparation.runtime_models import PreparationAction, PreparationBudget
from app.course_preparation.tool_registry import ToolRegistry
from app.course_preparation.tool_dispatcher import ToolDispatcher
from tests.course_preparation.test_runtime_foundation import Args, request, repo


def test_stage_prerequisites_no_progress_and_terminal_immutability(runtime_engine):
    service = repo(runtime_engine)
    value = service.submit('alice', request())
    claim = service.claim('worker')
    with pytest.raises(ValueError, match='PREREQUISITE'):
        service.transition(claim, 'research_scope', reason='no uploads')
    with pytest.raises(ValueError, match='ILLEGAL'):
        service.transition(claim, 'commit')
    service.checkpoint(claim, {'brief': {'goal': 'interview'}})
    updated = service.transition(claim, 'research_scope', reason='no uploads')
    service.checkpoint(updated, updated.checkpoint)
    service.checkpoint(updated, updated.checkpoint)
    with pytest.raises(NoProgress):
        service.checkpoint(updated, updated.checkpoint)
    service.fail(updated, 'NO_PROGRESS')
    with pytest.raises(StaleLease):
        service.checkpoint(updated, {'pretend_success': True})
    assert service.get_public('alice', value['preparation_id'])['status'] == 'failed'


def test_cancel_revision_conflict_and_public_owner_isolation(runtime_engine):
    service = repo(runtime_engine)
    value = service.submit('alice', request())
    with pytest.raises(LookupError):
        service.get_public('bob', value['preparation_id'])
    claim = service.claim('worker')
    with pytest.raises(RevisionConflict):
        service.cancel('alice', claim.preparation_id, expected_revision=1)
    assert service.get_public('alice', claim.preparation_id)['status'] == 'running'


def test_deadline_survives_retry_and_wait_releases_slot(runtime_engine):
    now = [datetime.now(timezone.utc)]
    service = repo(runtime_engine, now)
    value = service.submit('alice', request(), limits=BudgetLimits(seconds=200))
    claim = service.claim('worker')
    service.release(claim, delay_seconds=30)
    assert service.claim('other') is None
    now[0] += timedelta(seconds=31)
    newer = service.claim('other')
    assert newer and newer.lease_token != claim.lease_token
    service.fail(newer, 'PROVIDER_UNAVAILABLE')
    deadline = service.get_public('alice', claim.preparation_id)['budget']['deadline']
    assert service.retry('alice', claim.preparation_id)['budget']['deadline'] == deadline
    now[0] += timedelta(seconds=200)
    assert service.claim('expired') is None
    assert service.get_public('alice', value['preparation_id'])['error_code'] == 'DEADLINE_EXCEEDED'


def test_unknown_write_reconciles_receipt_without_resubmission(runtime_engine):
    service = repo(runtime_engine)
    service.submit('alice', request())
    claim = service.claim('worker')
    writes = []
    def handler(args, context, operation_id):
        writes.append(operation_id)
        return {'child_job_id': operation_id}
    registry = ToolRegistry([ToolSpec('generate', Args, handler, readonly=False,
                                     reconcile=lambda args, ctx, key: {'child_job_id': key})])
    mounted = registry.mount(claim)
    action = service.begin_action(claim, 'tool:call1', 'generate',
        {'arguments': {'value': 1}, 'tool_set_digest': mounted.digest}, BudgetCost(calls=1))
    result = ToolDispatcher(registry, service).dispatch(claim, [ToolCall(call_id='call1', name='generate', arguments={'value': 1})])
    assert not writes and result['results'] == [{'child_job_id': action['action_id']}]


def test_postgres_concurrent_reservation_cannot_overspend(runtime_engine):
    if runtime_engine.dialect.name != 'postgresql':
        pytest.skip('row locks require PostgreSQL')
    service = repo(runtime_engine)
    service.submit('alice', request(), limits=BudgetLimits(calls=1))
    claim = service.claim('worker')
    barrier = Barrier(2)
    def reserve(key):
        barrier.wait()
        try:
            service.begin_action(claim, key, 'read', {}, BudgetCost(calls=1))
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(reserve, ['a', 'b']))
    assert sum(outcomes) == 1
    with Session(runtime_engine) as session:
        budget = session.get(PreparationBudget, claim.preparation_id)
        assert budget.reserved['calls'] == 1
        assert len(session.scalars(select(PreparationAction)).all()) == 1


def test_revoked_source_stops_worker_but_owner_can_read_error_and_events(runtime_engine):
    service = repo(runtime_engine)
    value = service.submit('alice', request())
    context = service.claim('worker')
    service.authorizer.authorize = lambda *args: (_ for _ in ()).throw(PermissionError('revoked'))
    with pytest.raises(PermissionError):
        service.checkpoint(context, {'revoked_body': 'must not save'})
    service.fail(context, 'SOURCE_OR_OWNER_UNAVAILABLE')
    assert service.get_public('alice', value['preparation_id'])['error_code'] == 'SOURCE_OR_OWNER_UNAVAILABLE'
    assert service.events(owner_user_id='alice', preparation_id=value['preparation_id'])[-1].type == 'failed'


def test_unknown_read_retry_consumes_another_call(runtime_engine):
    service = repo(runtime_engine)
    service.submit('alice', request())
    claim = service.claim('worker')
    registry = ToolRegistry([ToolSpec('read', Args, lambda *args: {'body': 'known'})])
    mounted = registry.mount(claim)
    service.begin_action(claim, 'tool:read1', 'read', {'arguments': {'value': 1}, 'tool_set_digest': mounted.digest}, BudgetCost(calls=1))
    ToolDispatcher(registry, service).dispatch(claim, [ToolCall(call_id='read1', name='read', arguments={'value': 1})])
    assert service.get_public('alice', claim.preparation_id)['budget']['consumed']['calls'] == 2
