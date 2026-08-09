from __future__ import annotations

import json
import time

from langgraph.config import get_config, get_stream_writer

from app.chat.runtime.agent_tools import ToolExecutionContext
from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.nodes.constants import _TOOL_NAMES_CN


def executor_node(state: AgentState) -> dict:
    writer = get_stream_writer()
    rt = get_config()["configurable"]["runtime"]
    ctx: ToolExecutionContext = rt["ctx"]

    messages: list = _inject_reflect_hint(state["messages"], state)
    messages = _inject_plan_step_hint(messages, state)

    t_start: float = rt["t_start"]
    timeout_seconds: float = rt["timeout_seconds"]
    agent_gateway = rt["agent_gateway"]
    tool_schemas: list = _filter_tool_schemas_for_step(rt["tool_schemas"], state)
    tool_schemas = _filter_unrequested_image_search(
        tool_schemas,
        state,
        rt["request"],
    )
    tool_schemas = _filter_completed_retrieval_tools(tool_schemas, ctx)

    # Emit plan step "running" at start of each executor turn (guided mode)
    _emit_step_running(writer, state)

    mandatory_retrieval_calls = _build_mandatory_retrieval_calls(state, rt, ctx)
    if mandatory_retrieval_calls:
        tool_names_cn = [
            _TOOL_NAMES_CN.get(call["name"], call["name"])
            for call in mandatory_retrieval_calls
        ]
        print(
            f"[智能体] 强制检索 | {'、'.join(tool_names_cn)}",
            flush=True,
        )
        for call in mandatory_retrieval_calls:
            writer({
                "type": "tool_call",
                "payload": {"tool": call["name"], "args": call["args"]},
            })
        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["args"], ensure_ascii=False),
                    },
                }
                for call in mandatory_retrieval_calls
            ],
        }
        return {"messages": state["messages"] + [assistant_msg]}

    retrieval_failure = _required_retrieval_failure(state, ctx)
    if retrieval_failure:
        message = retrieval_failure["message"]
        ctx.trace["retrieval_gate"] = {
            "status": "blocked",
            "tool": retrieval_failure["tool"],
            "reason": retrieval_failure["reason"],
        }
        writer({"type": "delta", "payload": {"content": message}})
        writer({
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": message},
                "conversation": {
                    "conversation_id": rt.get("conv_id")
                    or (getattr(rt["request"], "conversation_id", "") or "")
                },
                "action": {"name": "agent.retrieval_incomplete"},
                "artifacts": [],
                "workflow": None,
                "sources": list(state.get("retrieval_sources") or []),
                "trace": ctx.trace,
                "tool_exchange": state["tool_exchange"],
            },
        })
        return {
            "messages": state["messages"]
            + [{"role": "assistant", "content": message}],
            "reflect_verdict": "",
            "reflect_hint": "",
            "reflect_filtered": {},
        }

    if (time.perf_counter() - t_start) > timeout_seconds:
        # Retrieval/embedding latency can legitimately consume the whole ReAct
        # budget. Once every required source has produced evidence, allow one
        # final LLM turn instead of falling back and repeating the same search.
        if (
            _required_retrieval_satisfied(ctx)
            and not ctx.trace.get("retrieval_finalization_grace_used")
        ):
            ctx.trace["retrieval_finalization_grace_used"] = True
        else:
            writer({"type": "__internal_fallback__", "reason": "react_timeout"})
            return {"fallback_reason": "react_timeout"}

    stream_fn = getattr(agent_gateway, "stream_chat_with_tools", None)
    if not callable(stream_fn):
        writer({"type": "__internal_fallback__", "reason": "gateway_no_tools_support"})
        return {"fallback_reason": "gateway_no_tools_support"}

    # Step count = number of assistant messages already in history + 1
    step = len([m for m in messages if m.get("role") == "assistant"]) + 1
    t_llm = time.perf_counter()
    t_first: float | None = None
    tool_calls_event = None
    answer_chunks: list[str] = []
    should_fallback: str | None = None

    for e in stream_fn(
        messages,
        tool_schemas,
        tool_choice="auto",
        temperature=0.1,
        max_tokens=2048,
    ):
        etype = e["type"]
        if etype == "text_delta":
            if t_first is None:
                t_first = time.perf_counter()
                print(f"[智能体] 第{step}轮 | ttft {(t_first - t_llm) * 1000:.0f}ms", flush=True)
            answer_chunks.append(e["content"])
            writer({"type": "delta", "payload": {"content": e["content"]}})
        elif etype == "tool_calls":
            tool_calls_event = e
        elif etype == "error":
            should_fallback = f"llm_error: {e['message']}"
            break
        elif etype == "unsupported":
            should_fallback = "unsupported_function_calling"
            break

    if should_fallback:
        writer({"type": "__internal_fallback__", "reason": should_fallback})
        return {"fallback_reason": should_fallback}

    llm_ms = round((time.perf_counter() - t_llm) * 1000)

    if tool_calls_event is not None:
        calls = tool_calls_event["calls"]
        tool_names_cn = [_TOOL_NAMES_CN.get(c["name"], c["name"]) for c in calls]
        print(f"[智能体] 第{step}轮 | {llm_ms}ms  调用工具: {'、'.join(tool_names_cn)}", flush=True)

        for c in calls:
            writer({"type": "tool_call", "payload": {"tool": c["name"], "args": c["args"]}})

        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": c.get("id") or f"call_{c['name']}",
                    "type": "function",
                    "function": {
                        "name": c["name"],
                        "arguments": json.dumps(c["args"], ensure_ascii=False),
                    },
                }
                for c in calls
            ],
        }
        # Persist original history + new assistant msg only; injected system hints
        # (reflect_hint / plan_step_hint) are transient — given to LLM this turn only.
        return {"messages": state["messages"] + [assistant_msg]}

    # Final answer turn — emit result event and finish
    answer = "".join(answer_chunks)
    # If this turn invoked draft_outline, append the structured outline_markdown to
    # the assistant answer. LLMs (esp. Qwen / DeepSeek) tend to strip # / ## / ###
    # symbols when reproducing markdown, losing visual hierarchy. We append server-side
    # to guarantee structure, and stream the appended portion as deltas so the
    # client sees a single continuous answer.
    outline_to_append = _maybe_outline_to_append(answer, state)
    if outline_to_append:
        appendix = "\n\n" + outline_to_append
        # Stream the appendix so the UI updates without a perceived jump
        for chunk_start in range(0, len(appendix), 64):
            writer({"type": "delta", "payload": {"content": appendix[chunk_start:chunk_start + 64]}})
        answer = answer + appendix

    total_ms = round((time.perf_counter() - t_start) * 1000)
    print(f"[智能体] 第{step}轮 | {llm_ms}ms  直接回答  总耗时={total_ms}ms", flush=True)

    ctx.trace["total_ms"] = total_ms
    request = rt["request"]
    resolved_conv_id = rt.get("conv_id") or (getattr(request, "conversation_id", "") or "")

    writer({
        "type": "result",
        "payload": {
            "message": {"role": "assistant", "content": answer},
            "conversation": {"conversation_id": resolved_conv_id},
            "action": {"name": "agent.reply"},
            "artifacts": [],
            "workflow": None,
            "sources": list(state.get("retrieval_sources") or []),
            "trace": ctx.trace,
            "tool_exchange": state["tool_exchange"],
        },
    })

    return {
        "messages": state["messages"] + [{"role": "assistant", "content": answer}],
        "reflect_verdict": "",  # clear after consuming
        "reflect_hint": "",
        "reflect_filtered": {},
    }


def _build_mandatory_retrieval_calls(state: AgentState, rt: dict, ctx: ToolExecutionContext) -> list[dict]:
    """Return deterministic retrieval calls required by the current UI state.

    Retrieval toggles are execution directives, not optional tool permissions:
    selected documents imply mandatory RAG, the full knowledge-base toggle
    implies mandatory RAG over all mounted document ids, and Web implies a
    mandatory web search. Planned generation tasks execute retrieval only when
    their current plan step reaches ``retrieve_context``.
    """
    capability = ctx.capability
    enabled_tools = {
        "rag_search": bool(getattr(capability, "allow_rag", False)),
        "web_search": bool(getattr(capability, "allow_web", False)),
    }
    already_executed = {
        str(step.get("tool") or "")
        for step in (ctx.trace.get("agent_steps") or [])
        if isinstance(step, dict)
    }

    current_plan = state.get("current_plan")
    if current_plan:
        steps = current_plan.get("steps") or []
        step_index = int(state.get("plan_step_index") or 0)
        if not (0 <= step_index < len(steps)):
            return []
        current_step = steps[step_index]
        expected_tools = set(current_step.get("expected_tools") or [])
        current_action = str(current_step.get("internal_action") or "")
        is_content_step = current_action in {"answer_question", "generate_resource"}
        required_tools = [
            tool_name
            for tool_name in ("rag_search", "web_search")
            if enabled_tools[tool_name]
            and (is_content_step or tool_name in expected_tools)
            and tool_name not in already_executed
        ]
        query = str(current_plan.get("subject") or "").strip()
    else:
        required_tools = [
            tool_name
            for tool_name in ("rag_search", "web_search")
            if enabled_tools[tool_name] and tool_name not in already_executed
        ]
        query = ""

    request = rt["request"]
    query = query or str(getattr(request, "question", "") or "").strip()
    if not query:
        return []

    calls = []
    for tool_name in required_tools:
        args = {"query": query}
        if tool_name == "rag_search":
            args["top_k"] = 5
        calls.append({
            "id": f"forced_{tool_name}_{len(already_executed) + len(calls) + 1}",
            "name": tool_name,
            "args": args,
        })
    return calls


def _required_retrieval_failure(state: AgentState, ctx: ToolExecutionContext) -> dict | None:
    """Block final answers when a user-required retrieval produced no evidence."""
    required = [
        tool_name
        for tool_name, enabled in (
            ("rag_search", bool(getattr(ctx.capability, "allow_rag", False))),
            ("web_search", bool(getattr(ctx.capability, "allow_web", False))),
        )
        if enabled
    ]
    if not required:
        return None

    trace_steps = [
        step
        for step in (ctx.trace.get("agent_steps") or [])
        if isinstance(step, dict)
    ]
    labels = {"rag_search": "知识库", "web_search": "网页"}
    for tool_name in required:
        matching = [step for step in trace_steps if step.get("tool") == tool_name]
        if not matching:
            continue
        latest = matching[-1]
        label = labels[tool_name]
        if not latest.get("ok"):
            return {
                "tool": tool_name,
                "reason": "tool_failed",
                "message": f"{label}检索未完成，暂时不能依据该来源回答。请稍后重试。",
            }
        if int(latest.get("evidence_count") or 0) < 1:
            return {
                "tool": tool_name,
                "reason": "no_evidence",
                "message": f"未找到可用于回答的{label}证据。请调整问题或资料范围后重试。",
            }
    return None


def _maybe_outline_to_append(answer: str, state: dict) -> str:
    """If this turn called draft_outline and the LLM didn't include markdown
    headers in its answer, return the outline_markdown to append. Otherwise
    return empty string."""
    import json as _json

    # LLM already produced structured markdown — don't double-append
    if "## " in answer or "\n#" in answer or "\n# " in answer:
        return ""

    # Check tool_exchange for a draft_outline call this turn
    called_outline_this_turn = False
    for msg in (state.get("tool_exchange") or []):
        if msg.get("role") != "assistant":
            continue
        for tc in (msg.get("tool_calls") or []):
            if (tc.get("function") or {}).get("name") == "draft_outline":
                called_outline_this_turn = True
                break
        if called_outline_this_turn:
            break
    if not called_outline_this_turn:
        return ""

    # active_draft_outline holds the latest outline content
    outline = (state.get("active_draft_outline") or {}).get("outline_markdown") or ""
    return str(outline).strip()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _filter_tool_schemas_for_step(tool_schemas: list, state: dict) -> list:
    """Keep mutation tools behind the current plan-step boundary.

    Strict mode exposes only the expected tools.  Guided mode remains flexible
    for retrieval/reflection, but generation tools stay hidden until the
    current step explicitly expects them.  This prevents a model from skipping
    outline confirmation and submitting an irreversible task early.
    """
    mode = state.get("plan_mode")
    if mode not in {"strict", "guided"}:
        return tool_schemas
    current_plan = state.get("current_plan")
    if not current_plan:
        return tool_schemas
    steps = current_plan.get("steps", [])
    idx = state.get("plan_step_index", 0)
    if not (0 <= idx < len(steps)):
        return tool_schemas
    expected = steps[idx].get("expected_tools") or []
    from app.chat.runtime.agent_tools.schemas import filter_schemas_by_step
    if mode == "strict":
        if not expected:
            return tool_schemas
        filtered = filter_schemas_by_step(tool_schemas, expected)
        return filtered if filtered else tool_schemas
    expected_set = set(expected)
    return [
        schema
        for schema in tool_schemas
        if not str((schema.get("function") or {}).get("name") or "").startswith(
            "generate_"
        )
        or (schema.get("function") or {}).get("name") in expected_set
    ]


def _filter_unrequested_image_search(tool_schemas: list, state: dict, request) -> list:
    """Hide image search unless the user or the current plan explicitly needs it.

    ``allow_image_search`` means the deployment can use the provider; it is not
    permission for an ordinary answer step to fetch an image opportunistically.
    Keeping the schema visible there caused a grounded RAG answer to detour into
    image search and exhaust the ReAct timeout before producing its final text.
    """
    current_plan = state.get("current_plan") or {}
    steps = current_plan.get("steps") or []
    idx = int(state.get("plan_step_index") or 0)
    current_step = steps[idx] if 0 <= idx < len(steps) else {}
    expected_tools = set(current_step.get("expected_tools") or [])
    plan_requests_images = (
        current_step.get("internal_action") == "fetch_visuals"
        or "image_search" in expected_tools
    )

    question = str(getattr(request, "question", "") or "")
    if not plan_requests_images:
        from app.chat.runtime.nodes.planner import _question_requests_visuals

        if _question_requests_visuals(question):
            plan_requests_images = True

    if plan_requests_images:
        return tool_schemas

    return [
        schema
        for schema in tool_schemas
        if ((schema.get("function") or {}).get("name") != "image_search")
    ]


def _filter_completed_retrieval_tools(
    tool_schemas: list,
    ctx: ToolExecutionContext,
) -> list:
    """Prevent a successful mandatory retrieval from being called twice."""
    completed = {
        str(step.get("tool") or "")
        for step in (ctx.trace.get("agent_steps") or [])
        if isinstance(step, dict)
        and step.get("ok")
        and int(step.get("evidence_count") or 0) > 0
    }
    completed &= {"rag_search", "web_search"}
    if not completed:
        return tool_schemas
    return [
        schema
        for schema in tool_schemas
        if (schema.get("function") or {}).get("name") not in completed
    ]


def _required_retrieval_satisfied(ctx: ToolExecutionContext) -> bool:
    required = {
        tool_name
        for tool_name, enabled in (
            ("rag_search", bool(getattr(ctx.capability, "allow_rag", False))),
            ("web_search", bool(getattr(ctx.capability, "allow_web", False))),
        )
        if enabled
    }
    if not required:
        return False
    completed = {
        str(step.get("tool") or "")
        for step in (ctx.trace.get("agent_steps") or [])
        if isinstance(step, dict)
        and step.get("ok")
        and int(step.get("evidence_count") or 0) > 0
    }
    return required.issubset(completed)


def _emit_step_running(writer, state: dict) -> None:
    """Emit plan_step_update 'running' when guided mode and a valid step exists."""
    if state.get("plan_mode") != "guided":
        return
    current_plan = state.get("current_plan")
    if not current_plan:
        return
    steps = current_plan.get("steps", [])
    idx = state.get("plan_step_index", 0)
    if not (0 <= idx < len(steps)):
        return
    writer({
        "type": "plan_step_update",
        "payload": {
            "step_index": idx,
            "status": "running",
            "user_title": steps[idx].get("user_title", ""),
        },
    })


def _inject_plan_step_hint(messages: list, state: dict) -> list:
    """In guided mode, inject current step info before the user message."""
    if state.get("plan_mode") != "guided":
        return messages
    current_plan = state.get("current_plan")
    if not current_plan:
        return messages
    steps = current_plan.get("steps", [])
    idx = state.get("plan_step_index", 0)
    if not (0 <= idx < len(steps)):
        return messages
    step = steps[idx]
    tools_str = "、".join(step.get("expected_tools", [])) or "无特定工具"
    extras = _build_visual_step_hint(step, state, idx)
    hint = (
        f"【当前执行步骤 {idx + 1}/{len(steps)}】\n"
        f"任务：{step.get('user_title', '')}\n"
        f"预期工具：{tools_str}\n"
        f"{extras}"
        "请专注完成此步骤，不要跳步。"
    )
    note = {"role": "system", "content": hint}
    if len(messages) >= 2:
        return messages[:-1] + [note, messages[-1]]
    return messages + [note]


def _build_visual_step_hint(step: dict, state: dict, step_idx: int) -> str:
    """Phase 6-B: for fetch_visuals steps, surface visual_need.query_candidates
    so the executor LLM uses pre-planned English keywords instead of inventing
    weak ones. On reflect retry, advance to the next unused candidate."""
    if step.get("internal_action") != "fetch_visuals":
        return ""
    visual_need = step.get("visual_need") or {}
    candidates = list(visual_need.get("query_candidates") or [])
    if not candidates:
        return ""

    # Pick a candidate based on how many times we've already retried this step
    # (each blocking retry from VisionReflector bumps retry_counts[key]).
    retry_counts = state.get("retry_counts") or {}
    retry_key = f"step_{step_idx}:image_search"
    attempt = int(retry_counts.get(retry_key, 0))
    chosen = candidates[min(attempt, len(candidates) - 1)]

    parts = [
        f"配图检索：调用 image_search(query=\"{chosen}\""
        f", count={visual_need.get('max_count', 3)}, "
        f"style=\"{visual_need.get('type', 'diagram')}\")。"
    ]
    if visual_need.get("purpose"):
        parts.append(f"目的：{visual_need['purpose']}")
    if attempt > 0:
        remaining = candidates[attempt + 1:]
        if remaining:
            parts.append(f"前次 query 未通过审查，本次切换 query。剩余候选：{remaining}")
    return "\n" + "\n".join(parts) + "\n"


def _inject_reflect_hint(messages: list, state: dict) -> list:
    """If reflect found an issue, prepend a system note so executor knows."""
    hint = state.get("reflect_hint", "")
    if not hint:
        return messages
    note = {"role": "system", "content": f"【上一步自检提示】{hint}"}
    if len(messages) >= 2:
        return messages[:-1] + [note, messages[-1]]
    return messages + [note]
