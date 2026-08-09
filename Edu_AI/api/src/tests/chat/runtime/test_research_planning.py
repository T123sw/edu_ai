from types import SimpleNamespace

from app.chat.domain.teaching_task_contract import TeachingTaskContract
from app.chat.runtime.nodes.executor import _build_mandatory_retrieval_calls
from app.chat.runtime.research.planner import (
    assess_evidence_coverage,
    build_research_plan,
)


def test_generation_research_plan_decomposes_teaching_evidence_needs():
    contract = TeachingTaskContract(
        intent="generate_single",
        topic="快速排序",
        resource_types=["report"],
        source_mode="course_auto",
    )

    plan = build_research_plan(contract)

    assert plan.primary_query == "快速排序"
    assert 3 <= len(plan.questions) <= 4
    assert {question.aspect for question in plan.questions} >= {
        "concept",
        "pedagogy",
        "misconception",
    }
    assert plan.max_supplemental_queries == 1


def test_coverage_reports_only_missing_aspects_and_next_query():
    contract = TeachingTaskContract(
        intent="generate_single",
        topic="快速排序",
        resource_types=["report"],
    )
    plan = build_research_plan(contract)

    coverage = assess_evidence_coverage(
        plan,
        "快速排序采用分治法。课堂活动可以演示分区过程，并设置学习目标。",
    )

    assert coverage.coverage_ratio >= 0.5
    assert "misconception" in coverage.missing_aspects
    assert "常见错误" in coverage.next_query


def test_executor_uses_one_bounded_supplemental_query_after_coverage_retry():
    state = {
        "current_plan": {
            "subject": "快速排序",
            "steps": [{
                "internal_action": "retrieve_context",
                "expected_tools": ["web_search"],
                "constraints": {
                    "research_plan": {
                        "max_supplemental_queries": 1,
                    }
                },
            }],
        },
        "plan_step_index": 0,
        "reflect_verdict": "retry",
        "reflect_filtered": {
            "research_coverage": {
                "next_query": "快速排序 常见错误 易错点",
                "supplemental_attempt": 1,
            }
        },
    }
    capability = SimpleNamespace(allow_rag=False, allow_web=True)
    ctx = SimpleNamespace(
        capability=capability,
        trace={"agent_steps": [{
            "tool": "web_search", "ok": True, "evidence_count": 3
        }]},
    )
    runtime = {
        "request": SimpleNamespace(question="生成快速排序报告"),
    }

    calls = _build_mandatory_retrieval_calls(state, runtime, ctx)

    assert len(calls) == 1
    assert calls[0]["name"] == "web_search"
    assert calls[0]["args"]["query"] == "快速排序 常见错误 易错点"


def test_executor_stops_supplemental_retrieval_when_budget_is_exhausted():
    state = {
        "current_plan": {
            "subject": "快速排序",
            "steps": [{
                "internal_action": "retrieve_context",
                "expected_tools": ["web_search"],
                "constraints": {"research_plan": {"max_supplemental_queries": 1}},
            }],
        },
        "plan_step_index": 0,
        "reflect_verdict": "retry",
        "reflect_filtered": {
            "research_coverage": {
                "next_query": "快速排序 常见错误 易错点",
                "supplemental_attempt": 2,
            }
        },
    }
    ctx = SimpleNamespace(
        capability=SimpleNamespace(allow_rag=False, allow_web=True),
        trace={"agent_steps": [{"tool": "web_search", "ok": True}]},
    )

    assert _build_mandatory_retrieval_calls(
        state, {"request": SimpleNamespace(question="q")}, ctx
    ) == []


def test_research_coverage_reflector_retries_once_then_degrades_with_warning():
    from app.chat.runtime.reflection.rules import ResearchCoverageReflector

    reflector = ResearchCoverageReflector()
    plan = build_research_plan(TeachingTaskContract(
        intent="generate_single", topic="快速排序", resource_types=["report"]
    ))
    constraints = {"research_plan": plan.model_dump(mode="json")}
    result = {
        "ok": True,
        "payload": {
            "summary": "快速排序是一种分治排序算法。",
            "sources": [{"title": "算法教材"}],
        },
    }

    first = reflector.evaluate("web_search", result, {}, constraints)
    second = reflector.evaluate(
        "web_search",
        result,
        {"reflect_filtered": first.filtered_data},
        constraints,
    )

    assert first.verdict == "retry"
    assert first.filtered_data["research_coverage"]["supplemental_attempt"] == 1
    assert second.verdict == "pass_with_warning"
    assert "预算已耗尽" in second.hint
