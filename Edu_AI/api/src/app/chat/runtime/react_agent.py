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
from app.chat.persistence.agent_run_store import get_agent_run_store
from app.chat.runtime.memory.manager import (
    build_agent_memory_context,
    update_agent_memory,
)
from app.chat.runtime.learning_context_prompt import build_learning_context_prompt
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
from app.chat.memory.domain import AgentMemoryContext
from app.chat.memory.service import AgentMemoryService
from app.chat.domain.route_decision import RouteDecision


_AGENT_FOLLOWUP_MARKERS = (
    "继续", "确认", "按这个", "就按", "开始", "没问题", "好的",
    "修改", "调整", "完善", "重试",
)
_ACTIVE_TASK_INTENTS = {"generate_single", "prepare_bundle", "modify", "confirm"}


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
        image_search_provider=None,   # None → image_search tool returns provider_not_configured
        workflow_registry=None,
        background_runner=None,
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
        agent_run_store=None,
    ):
        self.agent_gateway = agent_gateway
        self.fast_runtime = fast_runtime
        self.planner_gateway = planner_gateway
        self.vision_gateway = vision_gateway
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.image_search_provider = image_search_provider
        self.workflow_registry = workflow_registry or {}
        self.background_runner = background_runner
        self.max_steps = max_steps if max_steps is not None else Config.REACT_MAX_STEPS
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else Config.REACT_TIMEOUT_SECONDS
        self.agent_run_store = agent_run_store or get_agent_run_store()
        self._graph = build_graph()

    def run_stream(self, *, request, snapshot) -> Iterator[dict]:
        t_start = time.perf_counter()
        trace_id = str(uuid.uuid4())
        capability = getattr(snapshot, "capability", None)
        conv_id = getattr(request, "conversation_id", "") or str(uuid.uuid4())
        username = str(getattr(request, "owner", "") or "匿名")
        course_id = str(getattr(request, "course_id", "") or "")
        question = str(getattr(request, "question", "") or "")
        print(f"[智能体] 开始 | 用户={username}  问题=\"{question[:40]}\"", flush=True)

        actor_role = str(getattr(request, "actor_role", "teacher") or "teacher")
        tool_schemas = build_tool_schemas(capability, actor_role=actor_role)
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
        try:
            durable_state = self.agent_run_store.load(
                conv_id,
                owner_user_id=username,
                course_id=course_id,
            )
            # A live checkpoint is newer than the durable snapshot; after a
            # restart the durable state is the only available workflow memory.
            checkpoint_state = {**durable_state, **checkpoint_state}
            # Agent memory is updated after graph execution and persisted in
            # the durable store. Until the checkpoint is synchronized, its
            # stale value must not overwrite the latest durable memory.
            if durable_state.get("agent_memory"):
                checkpoint_state["agent_memory"] = durable_state["agent_memory"]
            active_draft_outline = checkpoint_state.get("active_draft_outline")
            current_pending_tasks = list(checkpoint_state.get("pending_tasks") or [])
        except Exception:
            pass

        # Ordinary questions belong to the normal chat runtime.  It already
        # applies enabled RAG/Web sources as answer context, while avoiding the
        # resource-generation planner, outline checks and visual-material SOP.
        # Extract against the restored state so confirmation/modification turns
        # for an active draft continue through the agent workflow.
        contract = extract_task_contract(
            request,
            capability,
            checkpoint_state,
            snapshot=snapshot,
        )
        prior_contract = dict(checkpoint_state.get("task_contract") or {})
        has_active_agent_task = bool(
            checkpoint_state.get("active_draft_outline")
            or str(prior_contract.get("intent") or "") in _ACTIVE_TASK_INTENTS
        )
        looks_like_agent_followup = has_active_agent_task and any(
            marker in question for marker in _AGENT_FOLLOWUP_MARKERS
        )
        if (
            contract.intent == "qa"
            and not contract.requires_images
            and not looks_like_agent_followup
        ):
            yield from self.fast_runtime.run_stream(
                request=request,
                snapshot=snapshot,
                decision=RouteDecision.fast(
                    action="chat.reply",
                    reason="ordinary_question",
                ),
            )
            return

        yield {"type": "status", "payload": {"stage": "thinking", "label": "正在分析请求..."}}

        needs_planning = should_plan(request, snapshot, checkpoint_state)

        agent_memory = dict(checkpoint_state.get("agent_memory") or {})
        messages = self._build_messages(
            request,
            snapshot,
            active_draft_outline=active_draft_outline,
            agent_memory=agent_memory,
        )

        # Shared execution context — passed via config to all nodes
        ctx = ToolExecutionContext(
            capability=capability,
            max_steps=self.max_steps,
            rag_retriever=self.rag_retriever,
            web_retriever=self.web_retriever,
            image_search_provider=self.image_search_provider,
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
        source_mode = str(getattr(capability, "source_mode", "") or "")
        if source_mode not in {"course_auto", "selected_documents", "none"}:
            if list(getattr(capability, "selected_doc_ids", []) or []):
                source_mode = "selected_documents"
            elif bool(getattr(capability, "allow_rag", False)):
                source_mode = "course_auto"
            else:
                source_mode = "none"
        ctx.trace["source_mode"] = source_mode
        ctx.trace["selected_doc_ids"] = list(
            getattr(capability, "selected_doc_ids", []) or []
        )

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
        # accumulated_images is the EXCEPTION: it must persist so that image_search
        # results from a prior turn (typically the post-outline turn) survive to the
        # next turn's generate_report. tools_node clears it explicitly when a new
        # draft_outline cycle begins.
        prior_accumulated_images = list(checkpoint_state.get("accumulated_images") or [])

        print(
            f"[智能体] needs_planning={needs_planning}  "
            f"active_draft_outline={'set' if active_draft_outline else 'none'}  "
            f"accumulated_images={len(prior_accumulated_images)}",
            flush=True,
        )

        initial_input = {
            "messages": messages,
            "tool_exchange": [],
            "retrieval_sources": [],
            "fallback_reason": "",
            "needs_planning": needs_planning,
            "task_contract": {},
            "logical_task_id": str(checkpoint_state.get("logical_task_id") or ""),
            "verification_report": {},
            "active_draft_outline": active_draft_outline,
            "pending_tasks": current_pending_tasks,
            "agent_memory": agent_memory,
            "current_plan": {},
            "plan_step_index": 0,
            "plan_mode": "",
            "reflect_verdict": "",
            "reflect_hint": "",
            "reflect_filtered": {},
            "retry_counts": {},
            "last_tool_results": [],
            "accumulated_images": prior_accumulated_images,
        }

        config = {"configurable": {"thread_id": conv_id, "runtime": rt}}

        try:
            for event in self._graph.stream(initial_input, config, stream_mode="custom"):
                if isinstance(event, dict) and event.get("type") == "__internal_fallback__":
                    yield from self._fallback(
                        request,
                        snapshot,
                        reason=event["reason"],
                        ctx=ctx,
                    )
                    self._persist_run_state(
                        conv_id, username, course_id, config, request=request
                    )
                    return
                yield event
            self._persist_run_state(
                conv_id, username, course_id, config, request=request
            )
        except Exception as exc:
            print(f"[智能体] 异常 | {exc}", flush=True)
            yield from self._fallback(
                request,
                snapshot,
                reason=f"react_error: {exc}",
                ctx=ctx,
            )
            self._persist_run_state(
                conv_id, username, course_id, config, request=request
            )

    def _build_messages(
        self,
        request,
        snapshot,
        *,
        active_draft_outline=None,
        agent_memory=None,
    ) -> list[dict]:
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

        system_messages = [
            {
                "role": "system",
                "content": build_system_content(
                    active_draft_outline,
                    actor_role=str(getattr(request, "actor_role", "teacher") or "teacher"),
                ),
            }
        ]
        learning_context = build_learning_context_prompt(
            getattr(snapshot, "learning_context", {})
        )
        if learning_context:
            system_messages.append({"role": "system", "content": learning_context})
        memory_context = build_agent_memory_context(agent_memory)
        if memory_context:
            system_messages.append({"role": "system", "content": memory_context})
        long_term_raw = getattr(snapshot, "agent_memory_context", {}) or {}
        if long_term_raw:
            long_term_prompt = AgentMemoryService.build_prompt(
                AgentMemoryContext.model_validate(long_term_raw)
            )
            if long_term_prompt:
                system_messages.append({"role": "system", "content": long_term_prompt})
        return [
            *system_messages,
            *history,
            {"role": "user", "content": str(getattr(request, "question", "") or "")},
        ]

    def _persist_run_state(
        self,
        conversation_id: str,
        owner_user_id: str,
        course_id,
        config: dict,
        *,
        request,
    ) -> None:
        """Persist only workflow state; conversation messages remain in the existing store."""
        try:
            graph_state = self._graph.get_state(config)
            values = graph_state.values if graph_state and graph_state.values else {}
            if values:
                values = dict(values)
                values["agent_memory"] = update_agent_memory(
                    values.get("agent_memory"),
                    user_message=str(getattr(request, "question", "") or ""),
                    task_contract=dict(values.get("task_contract") or {}),
                    state=values,
                )
                self._graph.update_state(
                    config,
                    {"agent_memory": values["agent_memory"]},
                )
                self.agent_run_store.save(
                    conversation_id, owner_user_id, course_id, values
                )
        except Exception as exc:
            print(f"[智能体] Agent run 状态持久化失败 | {exc}", flush=True)

    def _fallback(
        self,
        request,
        snapshot,
        *,
        reason: str,
        ctx: ToolExecutionContext | None = None,
    ) -> Iterator[dict]:
        print(f"[智能体] 降级 | 原因={reason}", flush=True)
        yield {"type": "status", "payload": {"stage": "fallback", "label": "切换到直接回答模式"}}
        from app.chat.domain.route_decision import RouteDecision
        decision = RouteDecision.fast(action="chat.reply", reason=reason)
        for event in self.fast_runtime.run_stream(
            request=request,
            snapshot=snapshot,
            decision=decision,
        ):
            if event.get("type") == "result" and ctx is not None:
                payload = dict(event.get("payload") or {})
                fast_trace = dict(payload.get("trace") or {})
                merged_trace = {
                    **fast_trace,
                    **ctx.trace,
                    "path": "agent_fallback",
                    "fallback_path": fast_trace.get("path") or "fast",
                    "fallback_reason": reason,
                }
                payload["trace"] = merged_trace
                event = {**event, "payload": payload}
            yield event
