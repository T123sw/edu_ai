from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.database.models import Base, PreparationBudget
from app.course_preparation.lifecycle_repository import StaleLease
from app.course_preparation.runtime_contracts import BudgetCost
from tests.course_preparation.test_generation_adapter import generation, spec


def test_manual_retry_adopts_unlimited_totals_and_keeps_usage_and_cancellation(generation):
    repo, parent, adapter = generation
    repo.retry_only = True
    repo.fail(parent, 'BUDGET_EXHAUSTED')
    with Session(repo.engine) as session, session.begin():
        budget = session.get(PreparationBudget, parent.preparation_id)
        spent = {key: budget.limits[key] for key in ('calls', 'tokens', 'cost_micro_usd')}
        budget.consumed = spent
    retried = repo.retry('alice', parent.preparation_id)
    assert retried['budget']['consumed'] == spent
    assert retried['budget']['deadline'] is None and retried['budget']['limits']['retry_only']
    # Expiring the historical timestamp cannot expire this execution.
    repo.clock = lambda: datetime.now(timezone.utc) + timedelta(days=2)
    context = repo.claim('retry', preparation_id=parent.preparation_id)
    assert context.deadline is None
    cost = BudgetCost(calls=1000, tokens=10_000_000, cost_micro_usd=100_000_000)
    action = repo.begin_action(context, 'large', 'generate_resource', spec(), cost)
    receipt = adapter.submit(context, spec(), action['action_id'])
    assert adapter.task_store.get_durable(receipt['job_id']).deadline_at is None
    repo.finish_action(context, action['action_id'], receipt, cost)
    assert repo.get_public('alice', parent.preparation_id)['budget']['consumed']['tokens'] == spent['tokens'] + cost.tokens
    child = adapter.artifacts.claim('alice', receipt['artifact_id'])
    adapter.artifacts.begin_action(child, 'child', 'model_completion', {}, cost)
    repo.cancel('alice', parent.preparation_id)
    with pytest.raises(StaleLease):
        adapter.artifacts.begin_action(child, 'late', 'model_completion', {}, cost)


@pytest.mark.parametrize('kind', ['sqlite', 'postgres'])
def test_queue_does_not_reintroduce_total_deadline_but_retains_attempt_limit(runtime_engine, tmp_path, kind):
    from app.chat.tasks.task_store import TaskStore
    from app.chat.tasks.postgres_task_store import PostgresTaskStore
    Base.metadata.create_all(runtime_engine, tables=[Base.metadata.tables['durable_tasks']])
    store = TaskStore(str(tmp_path / 'no-deadline.db')) if kind == 'sqlite' else PostgresTaskStore(runtime_engine)
    options = {'course_id': None, 'scope_type': 'preparation', 'scope_id': 'p',
               'config_snapshot_id': None, 'idempotency_key': None}
    for workflow in ('preparation_step', 'preparation_resource'):
        task = store.enqueue(task_id=workflow, workflow_type=workflow, owner_user_id='alice', handler_version=1,
            command={'preparation_id': 'p'}, max_attempts=2, deadline_at=None, **options)
        assert task.deadline_at is None and task.max_attempts == 2
    future = datetime.now(timezone.utc).timestamp() + 86400
    store.recover_expired_leases(now=future)
    for workflow in ('preparation_step', 'preparation_resource'):
        assert store.get_durable(workflow).deadline_at is None
        assert store.get_durable(workflow).status == 'pending'
    for attempt in (1, 2):
        for worker in ('one', 'two'):
            claimed = store.claim_next(lease_owner=worker, lease_seconds=10, now=future)
            assert claimed is not None and claimed.attempt_count == attempt
        future += 11
        store.recover_expired_leases(now=future)
    for workflow in ('preparation_step', 'preparation_resource'):
        assert store.get_durable(workflow).status == 'failed'
        assert store.get_durable(workflow).error_code == 'WORKER_LOST'
    standard = store.enqueue(task_id='ordinary', workflow_type='report_direct', owner_user_id='alice',
        handler_version=1, command={}, **options)
    assert standard.deadline_at is not None
    store.close()


def test_research_counters_remain_observable_without_exhausting_tools():
    from app.course_preparation.research_agent import ResearchAgent
    from app.course_preparation.research_contracts import ResearchState
    agent = ResearchAgent(model=None, sources=None, max_calls=None)
    state = ResearchState(calls=1000, searches=1000, reads=1000, upload_reads=100)
    assert agent.read_budget(state) == {'upload_reads': None, 'web_reads': None}
    assert agent.can_read('https://example.edu', state)
    assert agent.can_read('upload://large-document', state)
    assert 'search_sources' in [t['function']['name'] for t in agent.tools('research', state)]


def test_duration_never_invents_a_word_or_question_quota():
    from app.chat.harness.preparation_content import duration_constraint
    assert duration_constraint('report', {'node_budget_minutes': 1, 'resource_target_minutes': 1}) is None


def test_model_capacity_uses_provider_capabilities_and_unknown_fallback_is_conservative(monkeypatch):
    from types import SimpleNamespace
    from app.course_preparation.model_capacity import model_capacity
    official = {'api_base': 'https://api.deepseek.com/v1', 'model_name': 'deepseek-v4-flash'}
    assert model_capacity(SimpleNamespace(candidates=[official])) == (1_000_000, 384_000)
    assert model_capacity(SimpleNamespace(candidates=[{**official, 'api_base': 'https://unknown.test'}])) == (128_000, 12_000)
    assert model_capacity(SimpleNamespace(candidates=[official, {'model_name': 'unknown'}])) == (128_000, 12_000)
    from app.services import deepseek_key_failover
    proxy = 'http://127.0.0.1:15309/v1'
    monkeypatch.setattr(deepseek_key_failover, '_endpoints', {
        ('https://api.deepseek.com/v1', 'private-key', 'private-backup'): (proxy, 'private-token', None)})
    assert model_capacity(SimpleNamespace(candidates=[{**official, 'api_base': proxy}])) == (1_000_000, 384_000)
    assert deepseek_key_failover.upstream_base_url(proxy) == 'https://api.deepseek.com/v1'


def test_retry_only_all_generation_phases_use_provider_output_capacity(monkeypatch):
    from types import SimpleNamespace
    from app.course_preparation.harness_generation import PreparationHarnessGateway
    from app.course_preparation.harness_adapter import HarnessPreparationAdapter
    configured = SimpleNamespace(candidates=[{'api_base': 'https://api.deepseek.com/v1', 'model_name': 'deepseek-v4-flash'}])
    outputs = []
    def run(self, context, tools, **options):
        outputs.append(options['output_tokens'])
        return 'complete'
    monkeypatch.setattr(HarnessPreparationAdapter, '_run', run)
    root = PreparationHarnessGateway(configured, None, {}, deadline=None)
    assert root.context_tokens == 1_000_000
    assert root.for_phase('classroom_write', context={}).chat([], max_tokens=12000) == 'complete'
    assert root.for_phase('classroom_write', context={'operation': 'map_native_page'}).chat([], max_tokens=6000) == 'complete'
    assert outputs == [384_000, 384_000]
