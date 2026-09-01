from types import SimpleNamespace

from app.chat.evals.dataset import AgentEvalCase, CapabilityFixture, ExpectedOutcome
from app.chat.evals.evaluators import evaluate_case, summarize_results


def _case(**expected_overrides):
    expected = {
        "intent": "qa",
        "resource_types": [],
        "source_mode": "none",
        "plan_actions": ["answer_question", "verify", "report_result"],
        "required_tools": ["verify_task"],
        "forbidden_tools": ["generate_report"],
    }
    expected.update(expected_overrides)
    return AgentEvalCase(
        case_id="qa-basic-01",
        question="解释快速排序",
        dimensions=["intent", "planning"],
        capability=CapabilityFixture(),
        expected=ExpectedOutcome(**expected),
    )


def test_structural_evaluator_scores_contract_plan_and_tools():
    actual = SimpleNamespace(
        intent="qa",
        resource_types=[],
        source_mode="none",
    )
    plan = SimpleNamespace(
        steps=[
            SimpleNamespace(internal_action="answer_question", expected_tools=[]),
            SimpleNamespace(internal_action="verify", expected_tools=["verify_task"]),
            SimpleNamespace(internal_action="report_result", expected_tools=[]),
        ]
    )

    result = evaluate_case(_case(), actual_contract=actual, actual_plan=plan)

    assert result.passed is True
    assert result.score == 1.0
    assert result.failures == []


def test_structural_evaluator_reports_stable_failure_codes():
    actual = SimpleNamespace(
        intent="generate_single",
        resource_types=["report"],
        source_mode="course_auto",
    )
    plan = SimpleNamespace(
        steps=[SimpleNamespace(
            internal_action="generate_resource",
            expected_tools=["generate_report"],
        )]
    )

    result = evaluate_case(_case(), actual_contract=actual, actual_plan=plan)

    assert result.passed is False
    assert {failure.code for failure in result.failures} >= {
        "intent_mismatch",
        "resource_types_mismatch",
        "source_mode_mismatch",
        "plan_actions_mismatch",
        "missing_required_tool",
        "forbidden_tool_present",
    }


def test_summary_preserves_repeated_runs_and_failure_clusters():
    passing = evaluate_case(
        _case(),
        actual_contract=SimpleNamespace(intent="qa", resource_types=[], source_mode="none"),
        actual_plan=SimpleNamespace(steps=[
            SimpleNamespace(internal_action="answer_question", expected_tools=[]),
            SimpleNamespace(internal_action="verify", expected_tools=["verify_task"]),
            SimpleNamespace(internal_action="report_result", expected_tools=[]),
        ]),
        run_index=1,
    )
    failing = passing.model_copy(update={
        "passed": False,
        "score": 0.5,
        "failures": [{"code": "intent_mismatch", "message": "bad"}],
        "run_index": 2,
    })

    summary = summarize_results([passing, failing])

    assert summary.total_runs == 2
    assert summary.passed_runs == 1
    assert summary.pass_rate == 0.5
    assert summary.failure_clusters == {"intent_mismatch": 1}
