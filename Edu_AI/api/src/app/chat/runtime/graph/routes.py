from __future__ import annotations

from langgraph.graph import END

from app.chat.runtime.graph.state import AgentState

# ─── Entry routing ────────────────────────────────────────────────────────────

_PLAN_TRIGGER_KEYWORDS = (
    "生成", "制作", "写", "创建", "报告", "教案", "练习题",
    "方案", "计划", "调研", "分析", "设计", "实现",
)

_CONFIRM_KEYWORDS = (
    "好的", "可以", "确认", "开始", "生成", "ok", "OK", "没问题", "继续", "是的",
)


def should_plan(request, snapshot, state: dict) -> bool:
    # A deterministic contract controls planning.  This includes control turns
    # (status/cancel/modify) and QA turns whose user-selected sources make
    # retrieval mandatory, not only generation-keyword requests.
    try:
        from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
        capability = getattr(snapshot, "capability", None)
        contract = extract_task_contract(request, capability, state)
        if contract.intent != "qa" or contract.requires_rag or contract.requires_web:
            return True
    except Exception:
        # Keep the legacy keyword fallback for isolated callers and incomplete
        # test fixtures that do not provide capability state.
        question = str(getattr(request, "question", "") or "")
        if any(kw in question for kw in _PLAN_TRIGGER_KEYWORDS):
            return True
        if state.get("active_draft_outline") and any(kw in question for kw in _CONFIRM_KEYWORDS):
            return True

    # Reflect requested a bounded replan.
    if state.get("reflect_verdict") == "replan":
        return True

    return False


def route_entry(state: AgentState) -> str:
    """Conditional entry: go to planner if flagged, otherwise executor directly."""
    if state.get("needs_planning"):
        return "planner"
    return "executor"


# ─── Post-reflect routing ─────────────────────────────────────────────────────

def route_after_reflect(state: AgentState) -> str:
    """abort → END; replan → planner; everything else (pass/retry) → executor."""
    verdict = state.get("reflect_verdict", "")
    if verdict == "abort":
        return END
    if verdict == "replan":
        return "planner"
    return "executor"


# ─── Post-executor routing ────────────────────────────────────────────────────

def route_after_executor(state: AgentState) -> str:
    if state.get("fallback_reason"):
        return END
    msgs = state.get("messages") or []
    if msgs and msgs[-1].get("tool_calls"):
        return "tools"
    return END
