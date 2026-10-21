from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.course_preparation.lifecycle_repository import BudgetExceeded, StaleLease
from app.course_preparation.research_agent import ResearchError
from app.course_preparation.runner import PreparationRunner, StepResult
from app.course_preparation.runtime_contracts import BudgetCost, BudgetLimits
from app.course_preparation.runtime_models import PreparationExecution
from tests.course_preparation.test_runtime_foundation import repo, request


@pytest.mark.parametrize('code', ['PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'HARNESS_UNAVAILABLE'])
def test_provider_recovery_preserves_latest_checkpoint_and_spent_budget(runtime_engine, code):
    now = [datetime.now(timezone.utc)]
    repository = repo(runtime_engine, now)
    task = repository.submit('alice', request())
    task_id = task['preparation_id']

    def interrupted(context):
        action = repository.begin_action(context, 'model-request', 'read', {}, BudgetCost(calls=1))
        repository.finish_action(context, action['action_id'], {'ok': True})
        repository.checkpoint(context, {**context.checkpoint, 'evidence': ['already saved'], 'calls': 1})
        raise ResearchError(code, 'temporary outage')

    result = PreparationRunner(repository, {'normalize': interrupted}).run_step(task_id, worker_id='first')
    assert result['retrying'] and result['waiting']
    public = repository.get_public('alice', task_id)
    assert public['status'] == 'running' and public['error_code'] is None
    assert public['budget']['consumed']['calls'] == 1
    assert public['budget']['deadline'] == task['budget']['deadline']
    assert repository.claim('too-early', preparation_id=task_id) is None
    events = repository.events(owner_user_id='alice', preparation_id=task_id)
    assert events[-1].payload['reason'] == 'PROVIDER_RETRY'
    assert events[-1].payload['retry']['code'] == code
    now[0] += timedelta(seconds=5)

    def recovered(context):
        assert context.checkpoint['evidence'] == ['already saved']
        assert context.checkpoint['calls'] == 1
        return StepResult({**context.checkpoint, 'brief': {'goal': 'learn'}}, 'research_scope', 'NO_UPLOADS')

    # A fresh runner/repository simulates restarting the process during backoff.
    runner = PreparationRunner(repo(runtime_engine, now), {'normalize': recovered})
    assert runner.run_step(task_id, worker_id='restarted')['stage'] == 'research_scope'


def test_provider_retries_are_bounded_across_restarts_and_alternating_errors(runtime_engine):
    now = [datetime.now(timezone.utc)]
    repository = repo(runtime_engine, now)
    task_id = repository.submit('alice', request())['preparation_id']
    for index, code in enumerate(('PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT')):
        def fail(context):
            raise ResearchError(code, 'still unavailable')
        runner = PreparationRunner(repo(runtime_engine, now), {'normalize': fail})
        result = runner.run_step(task_id, worker_id=str(index))
        if index < 2:
            assert result['retrying']
            now[0] += timedelta(seconds=5 * (index + 1))
        else:
            assert result == {'failed': True, 'code': code}
    assert repository.get_public('alice', task_id)['status'] == 'failed'


@pytest.mark.parametrize('stage', ['produce', 'review', 'repair', 'commit'])
def test_analysis_recovery_does_not_replay_generation_or_nested_review(runtime_engine, stage):
    repository = repo(runtime_engine)
    repository.submit('alice', request())
    context = repository.claim('worker')
    assert repository.defer_provider_retry(context.model_copy(update={'stage': stage}), 'PROVIDER_TIMEOUT') is None


@pytest.mark.parametrize('error,expected', [
    (ResearchError('AGENT_NO_PROGRESS', 'invalid answer'), 'AGENT_NO_PROGRESS'),
    (ResearchError('BUDGET_EXHAUSTED', 'spent calls'), 'BUDGET_EXHAUSTED'),
    (PermissionError('revoked'), 'SOURCE_OR_OWNER_UNAVAILABLE'),
    (ValueError('bug'), 'STEP_FAILED'),
    (BudgetExceeded('DEADLINE_EXCEEDED'), 'DEADLINE_EXCEEDED'),
    (BudgetExceeded('BUDGET_EXHAUSTED:tokens'), 'BUDGET_EXHAUSTED'),
])
def test_terminal_failures_are_not_retried_or_mislabelled(runtime_engine, error, expected):
    repository = repo(runtime_engine)
    task_id = repository.submit('alice', request())['preparation_id']
    def fail(context):
        raise error
    result = PreparationRunner(repository, {'normalize': fail}).run_step(task_id, worker_id='worker')
    assert result == {'failed': True, 'code': expected}


def test_provider_recovery_obeys_deadline_and_preserves_progress(runtime_engine):
    now = [datetime.now(timezone.utc)]
    repository = repo(runtime_engine, now)
    task_id = repository.submit('alice', request(), limits=BudgetLimits(seconds=4))['preparation_id']
    def fail(context):
        repository.checkpoint(context, {'evidence': ['saved']})
        raise ResearchError('PROVIDER_TIMEOUT', 'timeout')
    result = PreparationRunner(repository, {'normalize': fail}).run_step(task_id, worker_id='worker')
    assert result == {'failed': True, 'code': 'DEADLINE_EXCEEDED'}
    with Session(runtime_engine) as session:
        assert session.get(PreparationExecution, (task_id, 1)).checkpoint == {'evidence': ['saved']}


def test_cancel_fences_pending_provider_recovery(runtime_engine):
    repository = repo(runtime_engine)
    task_id = repository.submit('alice', request())['preparation_id']
    context = repository.claim('worker')
    repository.cancel('alice', task_id)
    with pytest.raises(StaleLease):
        repository.defer_provider_retry(context, 'PROVIDER_TIMEOUT')
    assert repository.get_public('alice', task_id)['status'] == 'canceled'


def test_real_research_stages_resume_after_provider_failure_without_rereading_sources(runtime_engine):
    from app.course_preparation.research_agent import ResearchAgent
    from app.course_preparation.research_stages import ResearchStages
    from tests.course_preparation.test_research_flow import Model, Sources, request as research_request

    class InterruptedModel(Model):
        interrupted = False

        def decide(self, context, tools, *, timeout):
            if context['evidence'] and not self.interrupted:
                self.interrupted = True
                raise ResearchError('PROVIDER_TIMEOUT', 'response lost after source was read')
            return super().decide(context, tools, timeout=timeout)

    now = [datetime.now(timezone.utc)]
    repository = repo(runtime_engine, now)
    task_id = repository.submit('alice', research_request())['preparation_id']
    model, sources = InterruptedModel(), Sources()
    recovered = False
    for step in range(18):
        # Rebuild all workflow objects, retaining only SQL and the fake external services.
        repository = repo(runtime_engine, now)
        if repository.get_public('alice', task_id)['stage'] == 'produce':
            break
        stages = ResearchStages(repository, lambda *args: ResearchAgent(model=model, sources=sources), None)
        result = PreparationRunner(repository, stages.handlers()).run_step(task_id, worker_id=str(step))
        assert not result.get('failed'), result
        recovered = recovered or result.get('retrying', False)
        now[0] += timedelta(seconds=5)
    public = repository.get_public('alice', task_id)
    assert recovered and public['stage'] == 'produce'
    assert public['status'] == 'running' and public['result_ref'] is None
    assert len(sources.searches) == len(sources.reads) == 1
