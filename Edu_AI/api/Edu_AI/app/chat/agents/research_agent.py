from __future__ import annotations

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph, END

from ..service import GraphState


class ResearchAgent:
    def __init__(
        self,
        *,
        chat_tools_node: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        self._chat_tools_node = chat_tools_node
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("research_tools", self._chat_tools_node)
        graph.add_edge("research_tools", END)
        graph.set_entry_point("research_tools")
        return graph.compile()

    @property
    def graph(self):
        return self._graph

    def attach(self, graph: StateGraph, *, node_name: str = "research_agent") -> None:
        graph.add_node(node_name, self._graph)
