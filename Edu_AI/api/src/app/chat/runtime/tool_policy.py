"""Cost/quality-aware deterministic policy inside the compiled tool boundary."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCandidateDecision(BaseModel):
    tool: str
    required: bool
    cost_units: int
    quality_priority: int
    reason: str


class ToolPolicyDecision(BaseModel):
    selected_tools: list[str] = Field(default_factory=list)
    skipped_tools: dict[str, str] = Field(default_factory=dict)
    candidates: list[ToolCandidateDecision] = Field(default_factory=list)
    estimated_cost_units: int = 0
    supplemental: bool = False


_COST_UNITS = {"rag_search": 1, "web_search": 3}


def choose_retrieval_tools(
    *,
    enabled_tools: dict[str, bool],
    expected_tools: set[str],
    source_mode: str,
    already_executed: set[str],
    failed_tools: set[str],
    remaining_budget: int,
    supplemental: bool,
) -> ToolPolicyDecision:
    candidates: list[ToolCandidateDecision] = []
    skipped: dict[str, str] = {}
    for tool in ("rag_search", "web_search"):
        if not enabled_tools.get(tool, False):
            skipped[tool] = "capability_disabled"
            continue
        if tool not in expected_tools:
            skipped[tool] = "not_required_by_current_step"
            continue
        if tool in already_executed and not supplemental:
            skipped[tool] = "evidence_already_present"
            continue
        priority = _quality_priority(tool, source_mode, supplemental)
        candidates.append(ToolCandidateDecision(
            tool=tool,
            required=True,
            cost_units=_COST_UNITS[tool],
            quality_priority=priority,
            reason=(
                "补齐证据缺口" if supplemental
                else "UI 来源要求且当前步骤需要"
            ),
        ))
    candidates.sort(key=lambda item: (-item.quality_priority, item.cost_units, item.tool))
    selected = [candidate.tool for candidate in candidates[:max(0, remaining_budget)]]
    for candidate in candidates[len(selected):]:
        skipped[candidate.tool] = "tool_budget_exhausted"
    # Keep failed-tools information explicit in the decision record. Required
    # tools may still be retried by the bounded recovery policy; optional tools
    # were removed above because they are outside ``expected_tools``.
    for candidate in candidates:
        if candidate.tool in failed_tools:
            candidate.reason += "；上次失败，由恢复预算决定是否重试"
    return ToolPolicyDecision(
        selected_tools=selected,
        skipped_tools=skipped,
        candidates=candidates,
        estimated_cost_units=sum(_COST_UNITS[tool] for tool in selected),
        supplemental=supplemental,
    )


def _quality_priority(tool: str, source_mode: str, supplemental: bool) -> int:
    if tool == "rag_search":
        base = 100 if source_mode == "selected_documents" else 90
    else:
        base = 80 if source_mode == "none" else 70
    return base + (5 if supplemental else 0)
