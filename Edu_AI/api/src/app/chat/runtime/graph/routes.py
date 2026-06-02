from __future__ import annotations

from langgraph.graph import END

from app.chat.runtime.graph.state import AgentState

# ─── Entry routing ────────────────────────────────────────────────────────────

_PLAN_TRIGGER_KEYWORDS = (
    "生成", "制作", "写", "创建", "报告", "PPT", "ppt", "教案", "练习题",
    "方案", "计划", "调研", "分析", "设计", "实现",
)

_CONFIRM_KEYWORDS = (
    "好的", "可以", "确认", "开始", "生成", "ok", "OK", "没问题", "继续", "是的",
)


def should_plan(request, snapshot, state: dict) -> bool:
    question = str(getattr(request, "question", "") or "")

    # 1. Generation / design task keywords
    if any(kw in question for kw in _PLAN_TRIGGER_KEYWORDS):
        return True

    # 2. Active draft outline + user confirms → plan the generation step
    if state.get("active_draft_outline"):
        if any(kw in question for kw in _CONFIRM_KEYWORDS):
            return True

    # 3. Reflect requested a replan
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
