from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.chat.runtime.graph.routes import (
    route_after_executor,
    route_after_reflect,
    route_entry,
)
from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.nodes.executor import executor_node
from app.chat.runtime.nodes.planner import planner_node
from app.chat.runtime.nodes.reflect import reflect_node
from app.chat.runtime.nodes.tools import tools_node


_SHARED_CHECKPOINTER = None


def _build_checkpointer():
    """Process-level shared MemorySaver.

    ReActAgent is constructed per chat request (via build_orchestrator), which
    used to mean every request got a brand-new MemorySaver — making the
    LangGraph checkpoint useless across turns (active_draft_outline /
    accumulated_images vanished between user messages).

    Pinning the saver at module level keeps checkpoint state alive for the
    lifetime of the process. Server restarts still wipe it; a persistent
    checkpointer is planned per agent_architecture_design Phase 2-B.
    """
    global _SHARED_CHECKPOINTER
    if _SHARED_CHECKPOINTER is None:
        from langgraph.checkpoint.memory import MemorySaver
        _SHARED_CHECKPOINTER = MemorySaver()
    return _SHARED_CHECKPOINTER


def build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("tools", tools_node)
    graph.add_node("reflect", reflect_node)

    # Entry: planner if needs_planning, else straight to executor
    graph.add_conditional_edges(
        START, route_entry, {"planner": "planner", "executor": "executor"}
    )

    # Planner always hands off to executor
    graph.add_edge("planner", "executor")

    # Executor: call tools or finish
    graph.add_conditional_edges(
        "executor", route_after_executor, {"tools": "tools", END: END}
    )

    # Tools → reflect (always)
    graph.add_edge("tools", "reflect")

    # Reflect: abort → END; replan → planner; everything else → executor
    graph.add_conditional_edges(
        "reflect", route_after_reflect,
        {"executor": "executor", "planner": "planner", END: END},
    )

    return graph.compile(checkpointer=_build_checkpointer())
