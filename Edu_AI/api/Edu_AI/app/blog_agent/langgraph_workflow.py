from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from langgraph.graph import END, StateGraph

from .storage import load_task_state, save_task_state


def _compile_workflow(nodes: Dict[str, Any]):
    """构建并编译 LangGraph 工作流（两阶段 HITL）。

    节点：
    - planner_chapters -> wait_for_chapter_review -> planner_points -> wait_for_outline_review -> executor -> assembler
    """

    graph = StateGraph(dict)

    graph.add_node("planner_chapters", nodes["planner_chapters"])
    graph.add_node("wait_for_chapter_review", nodes["wait_for_chapter_review"])
    graph.add_node("planner_points", nodes["planner_points"])
    graph.add_node("wait_for_outline_review", nodes["wait_for_outline_review"])
    graph.add_node("executor", nodes["executor"])
    graph.add_node("assembler", nodes["assembler"])

    graph.set_entry_point("planner_chapters")

    graph.add_edge("planner_chapters", "wait_for_chapter_review")

    def _after_chapter_review(state: Dict[str, Any]):
        status = str(state.get("status") or "")
        if status == "waiting_for_chapter_review":
            return "end"
        return "planner_points"

    graph.add_conditional_edges(
        "wait_for_chapter_review",
        _after_chapter_review,
        {"end": END, "planner_points": "planner_points"},
    )

    graph.add_edge("planner_points", "wait_for_outline_review")

    def _after_outline_review(state: Dict[str, Any]):
        status = str(state.get("status") or "")
        if status == "waiting_for_outline_review":
            return "end"
        return "executor"

    graph.add_conditional_edges(
        "wait_for_outline_review",
        _after_outline_review,
        {"end": END, "executor": "executor"},
    )

    def _should_continue(state: Dict[str, Any]):
        try:
            outline = state.get("outline") or []
            idx = int(state.get("progress", {}).get("current_section_idx", 0))
            return "executor" if idx < len(outline) else "assembler"
        except Exception:
            return "assembler"

    graph.add_conditional_edges("executor", _should_continue, {"executor": "executor", "assembler": "assembler"})
    graph.add_edge("assembler", END)

    return graph.compile()


def run_blog_task_langgraph(
    thread_id: str,
    planner_chapters_func,
    wait_for_chapter_review_func,
    planner_points_func,
    wait_for_outline_review_func,
    executor_func,
    assembler_func,
):
    """以 LangGraph 方式执行任务。

    - 工作流状态为 dict
    - 每个节点内部负责把关键字段同步回 BlogTaskState 并落盘
    """

    state_model = load_task_state(thread_id)
    if state_model is None:
        return

    # 初始化 graph state：用 model_dump 作为 dict 载体
    graph_state: Dict[str, Any] = state_model.model_dump()

    workflow = _compile_workflow(
        {
            "planner_chapters": planner_chapters_func,
            "wait_for_chapter_review": wait_for_chapter_review_func,
            "planner_points": planner_points_func,
            "wait_for_outline_review": wait_for_outline_review_func,
            "executor": executor_func,
            "assembler": assembler_func,
        }
    )

    try:
        workflow.invoke(graph_state)
    except Exception as e:
        # 兜底：若 LangGraph 层抛异常，确保状态落盘
        st = load_task_state(thread_id)
        if st is None:
            return
        st.status = "failed"
        st.error_message = str(e)
        save_task_state(st)

