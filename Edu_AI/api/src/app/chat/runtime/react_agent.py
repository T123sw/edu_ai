"""P4-A ReAct Agent — LangGraph-based architecture.

Public API: ReActAgent.run_stream(*, request, snapshot) -> Iterator[dict]

SSE event sequence:
  {type: "status",       payload: {stage: "thinking", label: "..."}}
  {type: "delta",        payload: {content: "..."}}         <- streaming text
  {type: "tool_call",    payload: {tool: str, args: dict}}
  {type: "tool_result",  payload: {tool: str, summary: str, ok: bool}}
  {type: "task_submitted", payload: {task_id: str, workflow_type: str, message: str}}
  {type: "result",       payload: {...}}                     <- final result
"""
from __future__ import annotations

import time
import uuid
from typing import Iterator

from core.config import Config
from app.chat.runtime.agent_tools import ToolExecutionContext, build_tool_schemas
from app.chat.runtime.graph.builder import build_graph
from app.chat.runtime.graph.routes import should_plan
from app.chat.runtime.nodes.prompts import build_system_content


class ReActAgent:
    def __init__(
        self,
        *,
        agent_gateway,
        fast_runtime,
        planner_gateway=None,   # None → falls back to agent_gateway
        vision_gateway=None,    # None → VisionReflector disabled
        rag_retriever=None,
        web_retriever=None,
        workflow_registry=None,
        background_runner=None,
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ):
        self.agent_gateway = agent_gateway
        self.fast_runtime = fast_runtime
        self.planner_gateway = planner_gateway
        self.vision_gateway = vision_gateway
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.workflow_registry = workflow_registry or {}
        self.background_runner = background_runner
        self.max_steps = max_steps if max_steps is not None else Config.REACT_MAX_STEPS
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else Config.REACT_TIMEOUT_SECONDS
        self._graph = build_graph()

    def run_stream(self, *, request, snapshot) -> Iterator[dict]:
        t_start = time.perf_counter()
        trace_id = str(uuid.uuid4())
        capability = getattr(snapshot, "capability", None)
        conv_id = getattr(request, "conversation_id", "") or str(uuid.uuid4())
        username = str(getattr(request, "owner", "") or "匿名")
        question = str(getattr(request, "question", "") or "")
        print(f"[智能体] 开始 | 用户={username}  问题=\"{question[:40]}\"", flush=True)

        yield {"type": "status", "payload": {"stage": "thinking", "label": "正在分析请求..."}}

        tool_schemas = build_tool_schemas(capability)
        thread_config: dict = {"configurable": {"thread_id": conv_id}}

        # Read cross-turn working memory from checkpoint
        checkpoint_state: dict = {}
        active_draft_outline = None
        current_pending_tasks: list = []
        try:
            cs = self._graph.get_state(thread_config)
            checkpoint_state = cs.values if (cs and cs.values) else {}
            active_draft_outline = checkpoint_state.get("active_draft_outline")
            current_pending_tasks = list(checkpoint_state.get("pending_tasks") or [])
        except Exception:
            pass

        needs_planning = should_plan(request, snapshot, checkpoint_state)

        messages = self._build_messages(request, snapshot, active_draft_outline=active_draft_outline)

        # Shared execution context — passed via config to all nodes
        ctx = ToolExecutionContext(
            capability=capability,
            max_steps=self.max_steps,
            rag_retriever=self.rag_retriever,
            web_retriever=self.web_retriever,
            workflow_registry=self.workflow_registry,
            background_runner=self.background_runner,
            agent_gateway=self.agent_gateway,
            request=request,
            snapshot=snapshot,
        )
        ctx.trace["trace_id"] = trace_id
        ctx.trace["path"] = "agent"
        ctx.trace["_t_start"] = t_start
        ctx.trace["needs_planning"] = needs_planning

        effective_planner_gateway = self.planner_gateway or self.agent_gateway
        rt = {
            "agent_gateway": self.agent_gateway,
            "planner_gateway": effective_planner_gateway,
            "vision_gateway": self.vision_gateway,
            "capability": capability,
            "tool_schemas": tool_schemas,
            "request": request,
            "snapshot": snapshot,
            "t_start": t_start,
            "timeout_seconds": self.timeout_seconds,
            "ctx": ctx,
            # The conv_id resolved by run_stream() — used by executor for result events
            # so the client can persist a real conv_id even when the user didn't supply one.
            "conv_id": conv_id,
        }

        # Reset all per-turn transient state explicitly to avoid stale plan/reflect from
        # prior turns leaking into the new turn via the LangGraph checkpoint.
        initial_input = {
            "messages": messages,
            "tool_exchange": [],
            "fallback_reason": "",
            "needs_planning": needs_planning,
            "active_draft_outline": active_draft_outline,
            "pending_tasks": current_pending_tasks,
            "current_plan": {},
            "plan_step_index": 0,
            "plan_mode": "",
            "reflect_verdict": "",
            "reflect_hint": "",
            "reflect_filtered": {},
            "retry_counts": {},
            "last_tool_results": [],
        }

        config = {"configurable": {"thread_id": conv_id, "runtime": rt}}

        try:
            for event in self._graph.stream(initial_input, config, stream_mode="custom"):
                if isinstance(event, dict) and event.get("type") == "__internal_fallback__":
                    yield from self._fallback(request, snapshot, reason=event["reason"])
                    return
                yield event
        except Exception as exc:
            print(f"[智能体] 异常 | {exc}", flush=True)
            yield from self._fallback(request, snapshot, reason=f"react_error: {exc}")

    def _build_messages(self, request, snapshot, *, active_draft_outline=None) -> list[dict]:
        """Build message list from snapshot history with working memory in system prompt."""
        recent = list(getattr(snapshot, "recent_messages", []) or [])
        history = []
        for msg in recent:
            if isinstance(msg, dict):
                role = str(msg.get("role") or "user")
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")
                tool_call_id = msg.get("tool_call_id")
            else:
                role = str(getattr(msg, "role", "user") or "user")
                content = getattr(msg, "content", None)
                tool_calls = getattr(msg, "tool_calls", None)
                tool_call_id = getattr(msg, "tool_call_id", None)

            content_str = str(content) if content is not None else ""

            if role == "assistant" and tool_calls:
                history.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            elif role == "tool" and tool_call_id:
                history.append({"role": "tool", "tool_call_id": tool_call_id, "content": content_str})
            elif content_str:
                history.append({"role": role, "content": content_str})

        return [
            {"role": "system", "content": build_system_content(active_draft_outline)},
            *history,
            {"role": "user", "content": str(getattr(request, "question", "") or "")},
        ]

    def _fallback(self, request, snapshot, *, reason: str) -> Iterator[dict]:
        print(f"[智能体] 降级 | 原因={reason}", flush=True)
        yield {"type": "status", "payload": {"stage": "fallback", "label": "切换到直接回答模式"}}
        from app.chat.domain.route_decision import RouteDecision
        decision = RouteDecision.fast(action="chat.reply", reason=reason)
        yield from self.fast_runtime.run_stream(request=request, snapshot=snapshot, decision=decision)
