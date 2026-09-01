from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph, END


def route_after_supervisor(state: Dict[str, Any]) -> str:
    """两步路由后的分发策略（兼容渐进改造）。"""
    rt = str(state.get("response_type") or "chat")
    resource = str(state.get("resource_type") or "").strip().lower()

    if rt == "chat":
        return "chat"
    if rt == "research":
        return "research"

    if rt in {"text_generate", "multimodal_generate", "generate"}:
        if resource in {"video"}:
            return "video"
        if resource in {"podcast"}:
            return "podcast"
        return "text_generate"

    return "chat"


class SupervisorAgent:
    def __init__(self, router_node: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._router_node = router_node

    def attach(
        self,
        graph: StateGraph,
        *,
        chat_node: str,
        report_node: str,
        research_node: str,
        route_fn: Optional[Callable[[Dict[str, Any]], str]] = None,
        route_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        graph.add_node("supervisor", self._router_node)
        graph.set_entry_point("supervisor")

        if route_fn is None:
            def _default_route_fn(state: Dict[str, Any]) -> str:
                return state["response_type"]

            route_fn = _default_route_fn
        if route_mapping is None:
            route_mapping = {"chat": chat_node, "generate": report_node, "research": research_node}

        graph.add_conditional_edges("supervisor", route_fn, route_mapping)

    @staticmethod
    def attach_terminal_edges(graph: StateGraph, *, nodes: list[str]) -> None:
        for node in nodes:
            graph.add_edge(node, END)
