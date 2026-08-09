"""Rule-first structural evaluators for teacher-Agent runs."""
from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from pydantic import BaseModel, Field

from app.chat.evals.dataset import AgentEvalCase


class EvalFailure(BaseModel):
    code: str
    message: str


class EvalResult(BaseModel):
    case_id: str
    run_index: int = 1
    passed: bool
    score: float
    checks: dict[str, bool]
    failures: list[EvalFailure] = Field(default_factory=list)
    actual: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0


class EvalSummary(BaseModel):
    total_cases: int
    total_runs: int
    passed_runs: int
    pass_rate: float
    mean_score: float
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    failure_clusters: dict[str, int]


def evaluate_case(
    case: AgentEvalCase,
    *,
    actual_contract: Any,
    actual_plan: Any,
    run_index: int = 1,
) -> EvalResult:
    expected = case.expected
    actions, tool_sequence = _plan_facts(actual_plan)
    tools = set(tool_sequence)
    actual_resource_types = list(_value(actual_contract, "resource_types", []))
    actual_intent = str(_value(actual_contract, "intent", ""))
    actual_source_mode = str(_value(actual_contract, "source_mode", ""))
    actual_confirmation = str(_value(actual_contract, "confirmation_policy", ""))
    actual_topic = str(_value(actual_contract, "topic", ""))
    clarification = _value(actual_contract, "clarification", {})
    actual_needs_clarification = bool(_value(clarification, "required", False))

    checks = {
        "intent": actual_intent == expected.intent,
        "resource_types": actual_resource_types == expected.resource_types,
        "source_mode": actual_source_mode == expected.source_mode,
        "plan_actions": actions == expected.plan_actions,
        "required_tools": set(expected.required_tools).issubset(tools),
        "tool_order": _is_subsequence(expected.tool_order, tool_sequence),
        "forbidden_tools": not set(expected.forbidden_tools).intersection(tools),
        "confirmation_policy": (
            expected.confirmation_policy is None
            or actual_confirmation == expected.confirmation_policy
        ),
        "clarification": actual_needs_clarification == expected.needs_clarification,
        "topic": all(token in actual_topic for token in expected.expected_topic_contains),
    }
    failure_specs = {
        "intent": ("intent_mismatch", f"expected {expected.intent}, got {actual_intent}"),
        "resource_types": (
            "resource_types_mismatch",
            f"expected {expected.resource_types}, got {actual_resource_types}",
        ),
        "source_mode": (
            "source_mode_mismatch",
            f"expected {expected.source_mode}, got {actual_source_mode}",
        ),
        "plan_actions": (
            "plan_actions_mismatch", f"expected {expected.plan_actions}, got {actions}"
        ),
        "required_tools": (
            "missing_required_tool",
            f"required {expected.required_tools}, got {sorted(tools)}",
        ),
        "tool_order": (
            "tool_order_mismatch",
            f"expected order {expected.tool_order}, got {tool_sequence}",
        ),
        "forbidden_tools": (
            "forbidden_tool_present",
            f"forbidden {expected.forbidden_tools}, got {sorted(tools)}",
        ),
        "confirmation_policy": (
            "confirmation_policy_mismatch",
            f"expected {expected.confirmation_policy}, got {actual_confirmation}",
        ),
        "clarification": (
            "clarification_mismatch",
            f"expected required={expected.needs_clarification}, "
            f"got {actual_needs_clarification}",
        ),
        "topic": (
            "topic_mismatch",
            f"expected tokens {expected.expected_topic_contains}, got {actual_topic!r}",
        ),
    }
    failures = [
        EvalFailure(code=failure_specs[name][0], message=failure_specs[name][1])
        for name, passed in checks.items()
        if not passed
    ]
    passed_checks = sum(1 for passed in checks.values() if passed)
    score = passed_checks / len(checks) if checks else 1.0
    return EvalResult(
        case_id=case.case_id,
        run_index=run_index,
        passed=not failures,
        score=round(score, 4),
        checks=checks,
        failures=failures,
        actual={
            "intent": actual_intent,
            "resource_types": actual_resource_types,
            "source_mode": actual_source_mode,
            "confirmation_policy": actual_confirmation,
            "needs_clarification": actual_needs_clarification,
            "topic": actual_topic,
            "plan_actions": actions,
            "tools": tool_sequence,
        },
    )


def summarize_results(results: list[EvalResult]) -> EvalSummary:
    failure_codes: Counter[str] = Counter()
    for result in results:
        for failure in result.failures:
            code = failure.get("code", "unknown") if isinstance(failure, dict) else failure.code
            failure_codes[str(code)] += 1
    case_ids = {result.case_id for result in results}
    passed_runs = sum(1 for result in results if result.passed)
    total_runs = len(results)
    durations = sorted(result.duration_ms for result in results)
    return EvalSummary(
        total_cases=len(case_ids),
        total_runs=total_runs,
        passed_runs=passed_runs,
        pass_rate=round(passed_runs / total_runs, 4) if total_runs else 0.0,
        mean_score=(
            round(sum(result.score for result in results) / total_runs, 4)
            if total_runs else 0.0
        ),
        p50_ms=round(median(durations), 2) if durations else 0.0,
        p95_ms=round(_percentile(durations, 0.95), 2) if durations else 0.0,
        failure_clusters=dict(sorted(failure_codes.items())),
    )


def _plan_facts(plan: Any) -> tuple[list[str], list[str]]:
    steps = list(_value(plan, "steps", []) or [])
    actions: list[str] = []
    tools: list[str] = []
    for step in steps:
        actions.append(str(_value(step, "internal_action", "")))
        tools.extend(str(item) for item in (_value(step, "expected_tools", []) or []))
    return actions, tools


def _value(obj: Any, name: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return True
    index = 0
    for item in actual:
        if item == expected[index]:
            index += 1
            if index == len(expected):
                return True
    return False


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction
