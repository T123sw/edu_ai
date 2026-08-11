from __future__ import annotations

import json
import time

from langgraph.config import get_config, get_stream_writer

from app.chat.runtime.agent_tools import ToolExecutionContext
from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.nodes.constants import _TOOL_NAMES_CN
from app.chat.runtime.tool_policy import choose_retrieval_tools


def executor_node(state: AgentState) -> dict:
    writer = get_stream_writer()
    rt = get_config()["configurable"]["runtime"]
    ctx: ToolExecutionContext = rt["ctx"]
    ctx.current_plan = dict(state.get("current_plan") or {})

    # ``report_result`` is a terminal, server-owned plan step.  It must not be
    # delegated back to the model: after a generation task and verification
    # complete, the model can otherwise choose an unrelated status tool.  In
    # strict mode that call is rejected (the step deliberately allows no
    # tools), which used to replace a successful generation trace with an
    # abort result.  Finish deterministically and retain the complete audit.
    if _is_report_result_step(state):
        return _emit_compiled_report_result(writer, state, rt, ctx)
    if _is_clarification_step(state):
        return _emit_compiled_clarification(writer, state, rt, ctx)

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
    if not tool_schemas:
        messages = _prepare_tool_free_messages(messages)

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

    mandatory_plan_calls = _build_mandatory_plan_calls(state, rt, ctx)
    if mandatory_plan_calls:
        for call in mandatory_plan_calls:
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
                for call in mandatory_plan_calls
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

    tool_choice = _tool_choice_for_step(state, tool_schemas)
    for e in stream_fn(
        messages,
        tool_schemas,
        tool_choice=tool_choice,
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
    trace_steps = [
        step for step in (ctx.trace.get("agent_steps") or [])
        if isinstance(step, dict)
    ]
    already_executed = {
        str(step.get("tool") or "")
        for step in trace_steps
        if step.get("ok")
    }
    failed_tools = {
        str(step.get("tool") or "") for step in trace_steps if not step.get("ok")
    }
    supplemental = False

    current_plan = state.get("current_plan")
    if current_plan:
        steps = current_plan.get("steps") or []
        step_index = int(state.get("plan_step_index") or 0)
        if not (0 <= step_index < len(steps)):
            return []
        current_step = steps[step_index]
        expected_tools = set(current_step.get("expected_tools") or [])
        current_action = str(current_step.get("internal_action") or "")
        coverage_retry = dict(
            (state.get("reflect_filtered") or {}).get("research_coverage") or {}
        )
        supplemental_query = str(coverage_retry.get("next_query") or "").strip()
        supplemental_attempt = int(coverage_retry.get("supplemental_attempt") or 0)
        research_plan = dict(
            (current_step.get("constraints") or {}).get("research_plan") or {}
        )
        max_supplemental = int(research_plan.get("max_supplemental_queries") or 0)
        if supplemental_query and current_action == "retrieve_context":
            if supplemental_attempt > max_supplemental:
                return []
            query = supplemental_query
            supplemental = True
        else:
            is_content_step = current_action in {"answer_question", "generate_resource"}
            if is_content_step:
                expected_tools |= {
                    tool for tool, enabled in enabled_tools.items() if enabled
                }
            query = str(current_plan.get("subject") or "").strip()
    else:
        expected_tools = {
            tool_name for tool_name, enabled in enabled_tools.items() if enabled
        }
        query = ""

    request = rt["request"]
    query = query or str(getattr(request, "question", "") or "").strip()
    if not query:
        return []

    source_mode = str(getattr(capability, "source_mode", "") or "none")
    decision = choose_retrieval_tools(
        enabled_tools=enabled_tools,
        expected_tools=expected_tools,
        source_mode=source_mode,
        already_executed=already_executed,
        failed_tools=failed_tools,
        remaining_budget=max(
            0,
            int(getattr(ctx, "max_steps", 8)) - int(getattr(ctx, "step_count", 0)),
        ),
        supplemental=supplemental,
    )
    ctx.trace.setdefault("tool_decisions", []).append({
        **decision.model_dump(mode="json"),
        "query": query,
        "plan_step_index": int(state.get("plan_step_index") or 0),
    })

    calls = []
    for tool_name in decision.selected_tools:
        args = {"query": query}
        if tool_name == "rag_search":
            args["top_k"] = 5
        calls.append({
            "id": (
                f"supplement_{tool_name}_{supplemental_attempt}"
                if supplemental
                else f"forced_{tool_name}_{len(already_executed) + len(calls) + 1}"
            ),
            "name": tool_name,
            "args": args,
        })
    return calls


def _build_mandatory_plan_calls(
    state: AgentState,
    rt: dict,
    ctx: ToolExecutionContext,
) -> list[dict]:
    """Compile a single-authority strict step into its deterministic tool call."""

    if state.get("plan_mode") != "strict":
        return []
    plan = dict(state.get("current_plan") or {})
    steps = list(plan.get("steps") or [])
    index = int(state.get("plan_step_index") or 0)
    if not (0 <= index < len(steps)):
        return []
    step = dict(steps[index] or {})
    expected = list(step.get("expected_tools") or [])
    if len(expected) != 1:
        return []
    tool = str(expected[0] or "")
    if tool in {"rag_search", "web_search"}:
        return []
    if any(
        item.get("ok") and str(item.get("tool") or "") == tool
        for item in list(ctx.trace.get("agent_steps") or [])
        if isinstance(item, dict)
    ):
        return []

    contract = dict(plan.get("contract") or state.get("task_contract") or {})
    constraints = dict(contract.get("constraints") or {})
    active_outline = dict(state.get("active_draft_outline") or {})
    subject = str(plan.get("subject") or contract.get("topic") or "").strip()
    resource_type = str(
        active_outline.get("resource_type")
        or (contract.get("resource_types") or [plan.get("resource_type") or "report"])[0]
    )
    common = {
        "audience": str(contract.get("audience") or constraints.get("audience") or ""),
        "duration_minutes": int(
            contract.get("lesson_duration")
            or constraints.get("duration_minutes")
            or 45
        ),
    }
    if tool == "draft_outline":
        args = {
            "subject": subject,
            "resource_type": resource_type,
            # The public tool schema and the UI both treat this as readable
            # text.  Passing a dict rendered as ``[object Object]`` in the
            # execution card and made the audit trail needlessly opaque.
            "constraints": json.dumps(constraints, ensure_ascii=False),
            **common,
        }
    elif tool == "generate_report":
        args = {
            "subject": subject,
            "confirmed_outline": str(active_outline.get("outline_markdown") or ""),
            "focus": str(constraints.get("focus") or ""),
            "length_hint": str(constraints.get("length_hint") or ""),
        }
    elif tool == "generate_lesson_plan":
        args = {
            "subject": subject,
            "confirmed_outline": str(active_outline.get("outline_markdown") or ""),
            "grade": str(contract.get("audience") or constraints.get("grade") or ""),
            **common,
        }
    elif tool == "generate_quiz":
        args = {
            "subject": subject,
            "question_count": int(constraints.get("question_count") or 10),
            "difficulty": str(constraints.get("difficulty") or "medium"),
            "question_types": list(constraints.get("question_types") or []),
        }
    elif tool == "generate_classroom":
        args = {
            "topic": subject,
            "objectives": list(contract.get("teaching_goals") or []),
            "scene_count": int(constraints.get("scene_count") or 6),
            "teaching_style": str(constraints.get("teaching_style") or "guided"),
            "include_visuals": bool(constraints.get("include_visuals", True)),
            "enable_tts": bool(constraints.get("enable_tts", False)),
            "audience": common["audience"],
            "duration_minutes": int(
                contract.get("lesson_duration")
                or constraints.get("duration_minutes")
                or 25
            ),
        }
    elif tool.startswith("generate_"):
        args = {"topic": subject, "title": subject, **constraints}
    elif tool == "image_search":
        args = {"query": subject, "count": 6, "safe": True}
    elif tool in {
        "verify_task",
        "get_my_learning_progress",
        "get_course_learning_progress",
        "query_generation_job_status",
        "cancel_task",
    }:
        args = {}
        refs = dict(contract.get("conversation_refs") or {})
        if tool in {"get_my_learning_progress", "get_course_learning_progress"}:
            task_id = _first_unambiguous_domain_task_id(
                refs,
                (
                    "current_learning_task_ids",
                    "page_learning_task_ids",
                    "learning_task_ids",
                ),
                prefixes=("lt_",),
            )
        elif tool == "query_generation_job_status":
            task_id = _first_unambiguous_domain_task_id(
                refs,
                (
                    "current_generation_job_ids",
                    "page_generation_job_ids",
                    "generation_job_ids",
                ),
                prefixes=("job_",),
            )
        elif tool == "cancel_task":
            task_id = _first_unambiguous_domain_task_id(
                refs,
                (
                    "current_generation_job_ids",
                    "page_generation_job_ids",
                    "generation_job_ids",
                ),
                prefixes=("job_", "job-"),
            )
        else:
            task_id = ""
        if task_id:
            args["task_id"] = task_id
    else:
        return []
    return [{"id": f"compiled_step_{index + 1}_{tool}", "name": tool, "args": args}]


def _first_unambiguous_domain_task_id(
    refs: dict,
    keys: tuple[str, ...],
    *,
    prefixes: tuple[str, ...],
) -> str:
    """Select the highest-priority ID without hiding an invalid current ID."""
    for key in keys:
        raw_task_ids = list(
            dict.fromkeys(
                str(item or "").strip()
                for item in list(refs.get(key) or [])
                if str(item or "").strip()
            )
        )
        if not raw_task_ids:
            continue
        task_ids = [
            task_id for task_id in raw_task_ids if task_id.startswith(prefixes)
        ]
        if task_ids:
            return task_ids[0] if len(task_ids) == 1 else ""
        if key.startswith(("current_", "page_")):
            return raw_task_ids[0]
        return ""
    return ""


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


def _is_report_result_step(state: dict) -> bool:
    """Whether the compiled workflow has reached its deterministic terminal step."""
    plan = state.get("current_plan") or {}
    steps = plan.get("steps") or []
    index = int(state.get("plan_step_index") or 0)
    return (
        state.get("plan_mode") in {"guided", "strict"}
        and 0 <= index < len(steps)
        and str((steps[index] or {}).get("internal_action") or "") == "report_result"
    )


def _is_clarification_step(state: dict) -> bool:
    plan = state.get("current_plan") or {}
    steps = plan.get("steps") or []
    index = int(state.get("plan_step_index") or 0)
    return (
        state.get("plan_mode") in {"guided", "strict"}
        and 0 <= index < len(steps)
        and str((steps[index] or {}).get("internal_action") or "") == "clarify"
    )


def _emit_compiled_clarification(
    writer,
    state: AgentState,
    rt: dict,
    ctx: ToolExecutionContext,
) -> dict:
    """Ask the single compiler-approved high-impact clarification question."""
    plan = state.get("current_plan") or {}
    contract = dict(plan.get("contract") or state.get("task_contract") or {})
    clarification = dict(contract.get("clarification") or {})
    question = str(
        clarification.get("question")
        or "请补充一个会影响执行结果的关键信息。"
    ).strip()
    request = rt["request"]
    conversation_id = rt.get("conv_id") or (
        getattr(request, "conversation_id", "") or ""
    )
    ctx.trace["clarification"] = {
        "field": clarification.get("field"),
        "budget": clarification.get("budget", 1),
        "reason": clarification.get("reason", ""),
    }
    writer({"type": "delta", "payload": {"content": question}})
    writer({
        "type": "result",
        "payload": {
            "message": {"role": "assistant", "content": question},
            "conversation": {"conversation_id": conversation_id},
            "action": {"name": "agent.clarification_required"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": ctx.trace,
            "tool_exchange": state.get("tool_exchange") or [],
        },
    })
    return {
        "messages": list(state.get("messages") or [])
        + [{"role": "assistant", "content": question}],
        "reflect_verdict": "",
        "reflect_hint": "",
        "reflect_filtered": {},
    }


def _emit_compiled_report_result(
    writer,
    state: AgentState,
    rt: dict,
    ctx: ToolExecutionContext,
) -> dict:
    """Emit the terminal response without giving a completed plan new tool authority."""
    plan = state.get("current_plan") or {}
    steps = plan.get("steps") or []
    index = int(state.get("plan_step_index") or 0)
    step = dict(steps[index] or {})
    pending_tasks = list(state.get("pending_tasks") or [])
    verification = dict(
        getattr(ctx, "verification_report", None)
        or state.get("verification_report")
        or {}
    )
    if not verification and getattr(ctx, "artifact_readback", None) is not None:
        from app.chat.runtime.verification.plan_verifier import verify_plan_execution

        verification = verify_plan_execution(
            dict(plan),
            dict(getattr(ctx, "trace", {}) or {}),
            artifact_readback=getattr(ctx, "artifact_readback", None),
        ).model_dump(mode="json")
        ctx.verification_report = verification
    request = rt["request"]
    conversation_id = rt.get("conv_id") or (
        getattr(request, "conversation_id", "") or ""
    )

    readback = getattr(ctx, "artifact_readback", None)
    learning_message = _learning_status_message(state, ctx=ctx)
    if readback is not None and int(readback.get("checked") or 0) > 0:
        decision = str(verification.get("decision") or "partial")
        if decision == "pass":
            message = "任务已完成，产物可读，资源质量与执行审计均已通过。"
        else:
            repair = dict(verification.get("repair_directive") or {})
            reason = str(repair.get("reason") or "存在待处理的质量项")
            message = f"任务状态已核验，但尚不能宣称完整通过：{reason}。"
    elif learning_message:
        message = learning_message
    elif pending_tasks:
        message = _pending_task_submission_message(pending_tasks)
    else:
        message = "\u5df2\u5b8c\u6210\u4efb\u52a1\u7684\u5de5\u5177\u8c03\u7528\u4e0e\u7ed3\u6784\u5316\u5ba1\u8ba1\u3002"

    writer({
        "type": "plan_step_update",
        "payload": {
            "step_index": index,
            "status": "done",
            "user_title": step.get("user_title", ""),
        },
    })
    writer({"type": "delta", "payload": {"content": message}})
    writer({
        "type": "result",
        "payload": {
            "message": {"role": "assistant", "content": message},
            "conversation": {"conversation_id": conversation_id},
            "action": {"name": "agent.completed"},
            "artifacts": [],
            "workflow": None,
            "sources": list(state.get("retrieval_sources") or []),
            "trace": ctx.trace,
            "verification": verification,
            "tool_exchange": state.get("tool_exchange") or [],
        },
    })

    updated_steps = list(steps)
    updated_steps[index] = dict(step, status="done")
    return {
        "messages": list(state.get("messages") or [])
        + [{"role": "assistant", "content": message}],
        "current_plan": dict(plan, steps=updated_steps),
        "plan_step_index": index + 1,
        "reflect_verdict": "",
        "reflect_hint": "",
        "reflect_filtered": {},
    }


def _learning_status_message(state: dict, *, ctx=None) -> str:
    """Render role-scoped learning tool results without losing factual payloads."""
    results = list(
        getattr(ctx, "last_tool_results", None)
        or state.get("last_tool_results")
        or []
    )
    for item in reversed(results):
        tool_name = str((item or {}).get("tool_name") or "")
        if tool_name not in {
            "get_course_learning_progress",
            "get_my_learning_progress",
        }:
            continue
        result = dict((item or {}).get("raw_result") or {})
        if not result.get("ok"):
            return "学习记录暂不可用，请稍后重试。"
        payload = dict(result.get("payload") or {})
        if tool_name == "get_course_learning_progress":
            summaries = list(payload.get("task_summaries") or [])
            if not summaries:
                return "当前课程没有匹配的已发布学习任务记录。"
            lines: list[str] = []
            for raw in summaries:
                summary = dict(raw or {})
                title = str(summary.get("title") or summary.get("task_id") or "未命名任务")
                enrolled = int(summary.get("enrolled_students") or 0)
                started = int(summary.get("started_students") or 0)
                completed = int(summary.get("completed_students") or 0)
                rate = round(float(summary.get("completion_rate") or 0) * 100)
                basis = dict(summary.get("completion_basis_counts") or {})
                basis_parts = [
                    f"学生自报完成 {int(basis.get('self_reported') or 0)} 人",
                    f"活动证据完成 {int(basis.get('activity_evidenced') or 0)} 人",
                    f"测评验证完成 {int(basis.get('assessment_verified') or 0)} 人",
                ]
                basis_text = "、".join(
                    part for part in basis_parts if not part.endswith(" 0 人")
                ) or "尚无完成记录"
                lines.append(
                    f"《{title}》：课程学生 {enrolled} 人，已开始 {started} 人，"
                    f"已完成 {completed} 人，完成率 {rate}%。完成口径：{basis_text}。"
                )
            return "\n".join(lines) + "学生自报完成不等于测评通过或知识点已掌握。"

        completed_tasks = list(payload.get("completed_tasks") or [])
        pending = list(payload.get("pending_tasks") or [])
        if completed_tasks:
            task = dict(completed_tasks[0] or {})
            title = str(task.get("title") or task.get("task_id") or "未命名任务")
            task_id = str(task.get("task_id") or "")
            labels = {
                "self_reported": "学生自报完成",
                "activity_evidenced": "活动证据完成",
                "assessment_verified": "测评验证完成",
            }
            basis = labels.get(
                str(task.get("completion_basis") or ""),
                "完成口径未记录",
            )
            return (
                f"你刚完成的学习任务是《{title}》（{task_id}），完成口径：{basis}。"
                "学生自报完成不等于测评通过或知识点已掌握。"
                "下一步建议：复盘任务对应的课程资源和知识点，并在有测评时完成验证。"
            )
        if pending:
            task = dict(pending[0] or {})
            title = str(task.get("title") or task.get("task_id") or "未命名任务")
            return f"你当前待学习的任务是《{title}》，请先打开任务资源开始学习。"
        return "当前课程没有匹配的本人学习任务记录。"
    return ""


def _pending_task_submission_message(pending_tasks: list[dict]) -> str:
    """Describe every accepted task so bundle summaries stay truthful."""

    labels = {
        "report": "报告",
        "lesson_plan": "教案",
        "quiz": "练习题",
        "blog": "教学博客",
        "flashcard": "闪卡",
        "graph": "思维导图",
        "game": "课堂小游戏",
        "classroom": "AI 课堂",
    }
    unique: list[dict] = []
    seen: set[str] = set()
    for raw in pending_tasks:
        item = dict(raw or {})
        task_id = str(item.get("task_id") or "").strip()
        if not task_id or task_id in seen:
            continue
        seen.add(task_id)
        unique.append(item)
    if not unique:
        prefix = "已提交教学材料生成任务"
    elif len(unique) == 1:
        item = unique[0]
        task_id = str(item.get("task_id") or "")
        workflow = labels.get(
            str(item.get("workflow_type") or ""),
            str(item.get("workflow_type") or "资源"),
        )
        prefix = f"已提交{workflow}生成任务（任务 ID: {task_id}）"
    else:
        entries = []
        for item in unique:
            workflow = str(item.get("workflow_type") or "")
            label = labels.get(workflow, workflow or "资源")
            entries.append(f"{label}（{item.get('task_id')}）")
        prefix = f"已提交 {len(unique)} 个教学材料生成任务：" + "、".join(entries)
    return prefix + "。已完成工具调用与结构化审计，可继续询问任务进度。"


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
            return []
        filtered = filter_schemas_by_step(tool_schemas, expected)
        return filtered
    expected_set = set(expected)
    return [
        schema
        for schema in tool_schemas
        if not str((schema.get("function") or {}).get("name") or "").startswith(
            "generate_"
        )
        or (schema.get("function") or {}).get("name") in expected_set
    ]


def _prepare_tool_free_messages(messages: list[dict]) -> list[dict]:
    """Remove function-call protocol when the compiled step grants no tools.

    Some OpenAI-compatible providers infer another function call from earlier
    assistant/tool messages even when the current request contains no ``tools``
    field.  Preserve the observations as read-only context, but remove the
    protocol frames so an answer/confirmation step can only produce text.
    """

    prepared: list[dict] = []
    for message in messages:
        role = str(message.get("role") or "")
        if role == "assistant" and message.get("tool_calls"):
            content = str(message.get("content") or "").strip()
            if content:
                prepared.append({"role": "assistant", "content": content})
            continue
        if role == "tool":
            content = str(message.get("content") or "").strip()
            if content:
                prepared.append({
                    "role": "system",
                    "content": "已完成工具的只读结果：\n" + content,
                })
            continue
        prepared.append(dict(message))
    prepared.append({
        "role": "system",
        "content": (
            "当前计划步骤不授予任何工具权限。只根据已有上下文输出文本；"
            "不要请求、描述或伪造新的工具调用。"
        ),
    })
    return prepared


def _tool_choice_for_step(state: dict, tool_schemas: list) -> str:
    """Derive model tool authority from the current compiled plan step."""
    if not tool_schemas:
        return "none"
    current_plan = state.get("current_plan") or {}
    steps = current_plan.get("steps") or []
    idx = int(state.get("plan_step_index") or 0)
    step = steps[idx] if 0 <= idx < len(steps) else {}
    expected = list(step.get("expected_tools") or [])
    if state.get("plan_mode") == "strict" and len(expected) == 1:
        return "required"
    return "auto"


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
    """Emit plan_step_update 'running' for every compiled plan mode."""
    if state.get("plan_mode") not in {"guided", "strict"}:
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
