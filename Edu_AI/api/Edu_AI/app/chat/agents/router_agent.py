from __future__ import annotations

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph, END


class RouterAgent:
    def __init__(self, router_node: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._router_node = router_node

    def attach(self, graph: StateGraph, *, chat_node: str, report_entry: str) -> None:
        graph.add_node("router", self._router_node)
        graph.set_entry_point("router")
        graph.add_conditional_edges(
            "router",
            lambda s: s["response_type"],
            {"chat": chat_node, "generate": report_entry},
        )

    @staticmethod
    def attach_terminal_edges(graph: StateGraph, *, chat_node: str) -> None:
        graph.add_edge(chat_node, END)
