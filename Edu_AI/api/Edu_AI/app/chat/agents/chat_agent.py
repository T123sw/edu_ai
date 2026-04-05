from __future__ import annotations

from typing import Any, Callable, Dict

from langgraph.graph import StateGraph, END

from ..service import GraphState


class ChatAgent:
    def __init__(
        self,
        *,
        chat_node: Callable[[Dict[str, Any]], Dict[str, Any]],
        chat_tools_node: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        self._chat_node = chat_node
        self._chat_tools_node = chat_tools_node
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("chat", self._chat_node)
        graph.add_node("chat_tools", self._chat_tools_node)
        def _route_after_chat(state: Dict[str, Any]) -> str:
            messages = state.get("messages") or []
            if not messages:
                return "__end__"
            last_msg = messages[-1]
            tool_calls = getattr(last_msg, "tool_calls", None)
            if not tool_calls and isinstance(last_msg, dict):
                tool_calls = last_msg.get("tool_calls")
            return "tools" if tool_calls else "__end__"

        graph.add_conditional_edges(
            "chat",
            _route_after_chat,
            {"tools": "chat_tools", "__end__": END},
        )
        graph.add_edge("chat_tools", "chat")
        graph.set_entry_point("chat")
        return graph.compile()

    @property
    def graph(self):
        return self._graph

    def attach(self, graph: StateGraph, *, node_name: str = "chat_agent") -> None:
        graph.add_node(node_name, self._graph)
