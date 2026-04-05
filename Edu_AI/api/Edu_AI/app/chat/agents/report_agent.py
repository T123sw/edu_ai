from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from ..graph_state import GraphState
from .report_runtime import (
    ask_node_impl,
    outline_node_impl,
    generate_node_impl,
    extractor_node_impl,
    evaluator_node_impl,
)


class ReportAgent:
    """报告域代理：统一承载 report 子图装配与节点入口。"""

    def __init__(self, *, host: Any, extractor_system_prompt: str, max_clarification_turns: int, report_slot_schema: str) -> None:
        self._host = host
        self._extractor_system_prompt = str(extractor_system_prompt or "")
        self._max_clarification_turns = int(max_clarification_turns)
        self._report_slot_schema = str(report_slot_schema or "")
        self._graph = self._build_graph()

    @property
    def host(self) -> Any:
        return self._host

    # ===== 节点入口（统一挂载在 ReportAgent 内） =====
    def extractor_node(self, state: GraphState) -> GraphState:
        extractor_system_prompt = self.host._record_node_skills(
            state=state,
            node_name="extractor",
            base_prompt=self._extractor_system_prompt,
        )
        return extractor_node_impl(
            self.host,
            state,
            extractor_system_prompt=extractor_system_prompt,
            report_slot_schema=self._report_slot_schema,
        )

    def evaluator_node(self, state: GraphState) -> GraphState:
        return evaluator_node_impl(self.host, state, max_clarification_turns=self._max_clarification_turns)

    def ask_node(self, state: GraphState) -> GraphState:
        return ask_node_impl(self.host, state)

    def outline_node(self, state: GraphState) -> GraphState:
        return outline_node_impl(self.host, state)

    def generate_node(self, state: GraphState) -> GraphState:
        return generate_node_impl(self.host, state)

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("extractor", self.extractor_node)
        graph.add_node("evaluator", self.evaluator_node)
        graph.add_node("ask", self.ask_node)
        graph.add_node("outline", self.outline_node)
        graph.add_node("generate", self.generate_node)
        graph.add_edge("extractor", "evaluator")
        graph.add_conditional_edges(
            "evaluator",
            lambda s: s["response_type"],
            {"ask": "ask", "outline": "outline", "generate": "generate"},
        )
        graph.add_edge("ask", END)
        graph.add_edge("outline", END)
        graph.add_edge("generate", END)
        graph.set_entry_point("extractor")
        return graph.compile()

    @property
    def graph(self):
        return self._graph

    def attach(self, graph: StateGraph, *, node_name: str = "report_agent") -> None:
        graph.add_node(node_name, self._graph)
