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

    # Emit plan step "running" at start of each executor turn (guided mode)
    _emit_step_running(writer, state)

    if (time.perf_counter() - t_start) > timeout_seconds:
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
    total_ms = round((time.perf_counter() - t_start) * 1000)
    print(f"[智能体] 第{step}轮 | {llm_ms}ms  直接回答  总耗时={total_ms}ms", flush=True)

    ctx.trace["total_ms"] = total_ms
    request = rt["request"]

    writer({
        "type": "result",
        "payload": {
            "message": {"role": "assistant", "content": answer},
            "conversation": {"conversation_id": getattr(request, "conversation_id", "") or ""},
            "action": {"name": "agent.reply"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _filter_tool_schemas_for_step(tool_schemas: list, state: dict) -> list:
    """In strict mode, narrow tool_schemas to current step's expected_tools."""
    if state.get("plan_mode") != "strict":
        return tool_schemas
    current_plan = state.get("current_plan")
    if not current_plan:
        return tool_schemas
    steps = current_plan.get("steps", [])
    idx = state.get("plan_step_index", 0)
    if not (0 <= idx < len(steps)):
        return tool_schemas
    expected = steps[idx].get("expected_tools") or []
    if not expected:
        return tool_schemas
    from app.chat.runtime.agent_tools.schemas import filter_schemas_by_step
    filtered = filter_schemas_by_step(tool_schemas, expected)
    return filtered if filtered else tool_schemas


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
    hint = (
        f"【当前执行步骤 {idx + 1}/{len(steps)}】\n"
        f"任务：{step.get('user_title', '')}\n"
        f"预期工具：{tools_str}\n"
        "请专注完成此步骤，不要跳步。"
    )
    note = {"role": "system", "content": hint}
    if len(messages) >= 2:
        return messages[:-1] + [note, messages[-1]]
    return messages + [note]


def _inject_reflect_hint(messages: list, state: dict) -> list:
    """If reflect found an issue, prepend a system note so executor knows."""
    hint = state.get("reflect_hint", "")
    if not hint:
        return messages
    note = {"role": "system", "content": f"【上一步自检提示】{hint}"}
    if len(messages) >= 2:
        return messages[:-1] + [note, messages[-1]]
    return messages + [note]
