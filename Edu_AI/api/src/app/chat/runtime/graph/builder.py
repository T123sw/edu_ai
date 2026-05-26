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


def _build_checkpointer():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        from core.config import Config
        db_path = str(Config.STORAGE_ROOT / "agent_checkpoints.db")
        return SqliteSaver.from_conn_string(db_path)
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


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

    # Reflect: replan → planner; everything else → executor
    graph.add_conditional_edges(
        "reflect", route_after_reflect, {"executor": "executor", "planner": "planner"}
    )

    return graph.compile(checkpointer=_build_checkpointer())
