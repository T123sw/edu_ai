from types import SimpleNamespace
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.course_preparation.budget_meter import PreparationModelMeter
from app.course_preparation.lifecycle_repository import BudgetExceeded, StaleLease
from app.course_preparation.research_agent import ResearchError
from app.course_preparation.runtime_contracts import BudgetCost, BudgetLimits
from app.course_preparation.runtime_models import PreparationAction
from tests.course_preparation.test_runtime_foundation import repo, request


@pytest.mark.parametrize('outcome', ['settled', 'canceled', 'timeout'])
def test_model_reservation_waits_without_spending_or_ignoring_guards(runtime_engine, monkeypatch, outcome):
    import app.course_preparation.budget_meter as module
    service = repo(runtime_engine)
    service.submit('alice', request(), limits=BudgetLimits(calls=10, tokens=1000, cost_micro_usd=1000))
    context = service.claim('worker')
    held = service.begin_action(context, 'inflight', 'model_completion', {}, BudgetCost(calls=1, tokens=80, cost_micro_usd=800))
    clock, sleeps = [0.0], []

    def wait(seconds):
        sleeps.append(seconds); clock[0] += seconds
        if outcome == 'settled':
            service.finish_action(context, held['action_id'], {}, BudgetCost(calls=1, tokens=10, cost_micro_usd=100))
        elif outcome == 'canceled':
            service.cancel('alice', context.preparation_id)

    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: clock[0], sleep=wait), raising=False)
    meter = PreparationModelMeter(service, context)
    invoke = lambda: meter.start(input_upper_bound=40, output_limit=20, model='test', deadline=0.5)
    if outcome == 'settled':
        action = invoke()
        meter.finish(action, usage={'total_tokens': 20})
        assert len(sleeps) == 1
        budget = service.get_public('alice', context.preparation_id)['budget']
        assert budget['consumed'] == {'calls': 2, 'tokens': 30, 'cost_micro_usd': 300}
        assert not any(budget['reserved'].values())
    elif outcome == 'canceled':
        with pytest.raises(StaleLease): invoke()
        assert len(sleeps) == 1
    else:
        with pytest.raises(ResearchError, match='PROVIDER_TIMEOUT'): invoke()
        assert clock[0] == 0.5
    with Session(runtime_engine) as session:
        actions = list(session.scalars(select(PreparationAction)))
    assert len(actions) == (2 if outcome == 'settled' else 1)


def test_irrecoverable_budget_shortfall_never_waits_even_with_other_reservations(runtime_engine, monkeypatch):
    import app.course_preparation.budget_meter as module
    service = repo(runtime_engine)
    service.submit('alice', request(), limits=BudgetLimits(calls=2, tokens=1000, cost_micro_usd=1000))
    context = service.claim('worker')
    spent = service.begin_action(context, 'spent', 'model_completion', {}, BudgetCost(calls=1, tokens=60, cost_micro_usd=600))
    service.finish_action(context, spent['action_id'], {}, BudgetCost(calls=1, tokens=60, cost_micro_usd=600))
    service.begin_action(context, 'held', 'model_completion', {}, BudgetCost(calls=1, tokens=10, cost_micro_usd=100))
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: 0, sleep=lambda _: pytest.fail('hard deficit must not wait')), raising=False)
    with pytest.raises(BudgetExceeded):
        PreparationModelMeter(service, context).start(input_upper_bound=40, output_limit=20, model='test', deadline=10)
