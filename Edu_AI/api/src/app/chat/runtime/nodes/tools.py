from __future__ import annotations

import json
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

from langgraph.config import get_config, get_stream_writer

from app.chat.runtime.agent_tools import ToolExecutionContext, execute_tool
from app.chat.runtime.agent_tools.constants import TOOL_TO_WORKFLOW
from app.chat.runtime.agent_tools.tool_meta import is_parallel_safe
from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.nodes.constants import (
    _ARG_KEYS_CN,
    _OBSERVE_HINTS,
    _TOOL_NAMES_CN,
    _WORKFLOW_LABELS,
)


def _retrieval_source_key(source: dict) -> str:
    """Return a chunk-level identity without collapsing unrelated RAG hits."""
    chunk_id = str(source.get("chunk_id") or source.get("id") or "").strip()
    if chunk_id:
        return f"chunk:{chunk_id}"

    identity = "\0".join(
        str(source.get(key) or "").strip()
        for key in (
            "document_id",
            "source_path",
            "source",
            "url",
            "title",
            "content",
        )
    )
    return "source:" + hashlib.sha1(identity.encode("utf-8")).hexdigest()


def _fmt_tool_args(args: dict) -> str:
    parts = []
    for k, v in list(args.items())[:4]:
        if v is None or v == "" or v == []:
            continue
        if k == "confirmed_outline":
            v_str = str(v)
            parts.append(f"大纲=({len(v_str)}字)")
        else:
            v_str = str(v)
            if len(v_str) > 16:
                v_str = v_str[:16] + "..."
            parts.append(f"{_ARG_KEYS_CN.get(k, k)}={v_str!r}")
    return "  ".join(parts)


def _format_tool_result_for_context(tool_name: str, result: dict) -> str:
    if not result.get("ok"):
        return f"工具 {tool_name} 执行失败: {result.get('error', '未知错误')}"

    payload = result.get("payload", {})

    if tool_name == "rag_search":
        content = f"知识库检索结果：\n{payload.get('answer', '无内容')}"
        return content + _OBSERVE_HINTS["rag_search"]

    if tool_name == "web_search":
        content = f"联网检索结果：\n{payload.get('summary', '无内容')}"
        return content + _OBSERVE_HINTS["web_search"]

    if tool_name == "image_search":
        images = payload.get("images") or []
        trace = payload.get("trace") or {}
        content = (
            f"图片检索完成：候选 {len(images)} 张"
            f"（原始 {trace.get('raw_count', '?')}，过滤后 {trace.get('filtered_count', '?')}）。"
            f"VisionReflector 将审查相关性与质量。"
        )
        return content + _OBSERVE_HINTS["image_search"]

    if tool_name == "draft_outline":
        subject = payload.get("subject", "")
        # NOTE: do NOT ask the LLM to reproduce the outline. Qwen / DeepSeek strip
        # markdown header symbols (## / ###) and turn the outline into flat
        # numbered text, losing visual hierarchy. Instead the executor will
        # synthesize the final assistant message by appending outline_markdown
        # verbatim (see _maybe_append_outline in executor.py).
        return (
            f"已为《{subject}》生成大纲。请只用 1-2 句话告诉用户大纲已就绪，"
            "并询问是否需要调整或确认。**不要在回复中重复或改写大纲正文** — "
            "系统会自动把完整大纲附在你的回复后面。"
        )

    if tool_name in TOOL_TO_WORKFLOW:
        return f"已提交后台任务，task_id={payload.get('task_id', '')}"

    return result.get("summary", "")


def tools_node(state: AgentState) -> dict:
    writer = get_stream_writer()
    rt = get_config()["configurable"]["runtime"]
    ctx: ToolExecutionContext = rt["ctx"]

    last_msg = state["messages"][-1]
    tool_calls_openai = last_msg.get("tool_calls") or []

    calls = [
        {
            "id": tc.get("id"),
            "name": tc.get("function", {}).get("name") or "",
            "args": json.loads(tc.get("function", {}).get("arguments") or "{}"),
        }
        for tc in tool_calls_openai
    ]

    tool_results_msgs: list[dict] = []
    new_tool_exchange = list(state["tool_exchange"])
    new_retrieval_sources = list(state.get("retrieval_sources") or [])
    new_tool_exchange.append(last_msg)

    new_active_draft_outline = state.get("active_draft_outline")
    new_pending_tasks = list(state.get("pending_tasks") or [])
    ctx.pending_tasks = new_pending_tasks
    raw_results_for_reflect: list[dict] = []
    # Per-tools-node-invocation override: if any tool in this batch is draft_outline,
    # we reset accumulated_images so the new task starts fresh (set below after
    # the dispatch loop knows which tools ran).
    accumulated_images_override: list | None = None

    # Phase 6-A: expose accumulated visual assets (from prior image_search rounds
    # in this run) on ctx so handlers like generate_report can pick them up
    # and inject them into the produced artifact.
    ctx.accumulated_images = list(state.get("accumulated_images") or [])

    # Strict-mode validation: reject any call outside current step's expected_tools
    calls = _enforce_strict_mode(calls, state)

    tool_names = [c["name"] for c in calls]
    parallel_eligible = len(calls) > 1 and is_parallel_safe(tool_names)
    if parallel_eligible:
        print(f"[智能体] 并行执行 | {len(calls)}个工具: {'、'.join(tool_names)}", flush=True)
        executed = _execute_in_parallel(calls, ctx)
    else:
        executed = []
        for call in calls:
            if call.get("_rejected_reason"):
                from app.chat.runtime.agent_tools.result import error_result
                executed.append((call, error_result(call["name"], "strict_violation", call["_rejected_reason"]), 0))
                continue
            t_tool = time.perf_counter()
            result = execute_tool(call["name"], call["args"], ctx)
            tool_ms = round((time.perf_counter() - t_tool) * 1000)
            executed.append((call, result, tool_ms))

    for call, result, tool_ms in executed:
        tool_name = call["name"]
        tool_args = call["args"]
        call_id = call.get("id") or f"call_{tool_name}"

        print(f"[智能体] 调用 | {_TOOL_NAMES_CN.get(tool_name, tool_name)}  {_fmt_tool_args(tool_args)}", flush=True)
        raw_results_for_reflect.append({"tool_name": tool_name, "raw_result": result})

        ok_label = "成功" if result.get("ok") else "失败"
        summary = str(result.get("summary", ""))[:40]
        payload = result.get("payload") or {}
        if result.get("ok") and tool_name in {"rag_search", "web_search"}:
            known_source_keys = {
                _retrieval_source_key(source)
                for source in new_retrieval_sources
                if isinstance(source, dict)
            }
            for source in payload.get("sources") or []:
                if not isinstance(source, dict):
                    continue
                source_key = _retrieval_source_key(source)
                if source_key not in known_source_keys:
                    new_retrieval_sources.append(source)
                    known_source_keys.add(source_key)
        task_hint = (
            f"  任务={str(payload.get('task_id', ''))[:10]}"
            if isinstance(payload, dict) and payload.get("task_id")
            else ""
        )
        print(f"[智能体] 结果 | {ok_label}  {summary}  {tool_ms}ms{task_hint}", flush=True)

        # Forward structured payload extras for UI rendering (e.g. outline preview).
        # Keep keys minimal — full task results stay server-side.
        extras: dict = {}
        if tool_name == "draft_outline" and result.get("ok"):
            outline_md = str((payload or {}).get("outline_markdown") or "")
            if outline_md:
                extras["outline_markdown"] = outline_md
                extras["resource_type"] = str((payload or {}).get("resource_type") or "")
                extras["subject"] = str((payload or {}).get("subject") or "")
        writer({"type": "tool_result", "payload": {
            "tool": tool_name,
            "summary": result.get("summary", ""),
            "ok": result.get("ok", False),
            **extras,
        }})

        if result.get("ok") and tool_name in TOOL_TO_WORKFLOW:
            task_id = str(payload.get("task_id", ""))
            workflow_type = str(payload.get("workflow_type", ""))
            if task_id:
                label = _WORKFLOW_LABELS.get(workflow_type, "内容")
                writer({
                    "type": "task_submitted",
                    "payload": {
                        "task_id": task_id,
                        "workflow_type": workflow_type,
                        "message": f"正在后台生成{label}，可通过任务ID查询进度",
                    },
                })
                new_pending_tasks.append({"task_id": task_id, "workflow_type": workflow_type})
                ctx.pending_tasks = new_pending_tasks

        if tool_name == "draft_outline" and result.get("ok"):
            # Phase 6-A.2: remember whether the user asked for images at the
            # time of outline drafting, so the post-confirm turn can plan a
            # fetch_visuals step even when the confirm message itself ("继续"
            # / "生成") contains no visual keywords.
            from app.chat.runtime.nodes.planner import _question_requests_visuals
            origin_question = str(getattr(getattr(ctx, "request", None), "question", "") or "")
            new_active_draft_outline = _build_active_draft_outline(
                payload=payload,
                state=state,
                task_contract=getattr(ctx, "task_contract", None),
                needs_visuals=_question_requests_visuals(origin_question),
            )
            # A new draft_outline marks the start of a new task — discard any
            # leftover images from a previous generation cycle.
            accumulated_images_override = []

        tool_result_msg = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": _format_tool_result_for_context(tool_name, result),
        }
        tool_results_msgs.append(tool_result_msg)
        new_tool_exchange.append(tool_result_msg)

    updates: dict = {
        "messages": state["messages"] + tool_results_msgs,
        "tool_exchange": new_tool_exchange,
        "retrieval_sources": new_retrieval_sources,
        "active_draft_outline": new_active_draft_outline,
        "pending_tasks": new_pending_tasks,
        "last_tool_results": raw_results_for_reflect,
    }
    if getattr(ctx, "verification_report", None):
        updates["verification_report"] = dict(ctx.verification_report)
    if accumulated_images_override is not None:
        updates["accumulated_images"] = accumulated_images_override
    return updates


def _build_active_draft_outline(
    *,
    payload: dict,
    state: dict,
    task_contract: dict | None,
    needs_visuals: bool,
) -> dict:
    """Persist the whole confirmation scope, not only the previewed resource.

    A bundle uses one representative outline (normally the lesson plan) as its
    shared confirmation boundary.  Losing the original resource list here made
    a later ``确认生成`` look like a single lesson-plan request.
    """

    current_plan = dict(state.get("current_plan") or {})
    contract = dict(current_plan.get("contract") or task_contract or {})
    preview_type = str(payload.get("resource_type") or "report")
    resource_types = [
        str(item)
        for item in list(contract.get("resource_types") or [preview_type])
        if str(item or "").strip()
    ]
    return {
        "subject": str(payload.get("subject") or ""),
        "resource_type": preview_type,
        "resource_types": list(dict.fromkeys(resource_types)),
        "origin_intent": str(contract.get("intent") or "generate_single"),
        "outline_markdown": str(payload.get("outline_markdown") or ""),
        "needs_visuals": bool(needs_visuals),
    }


def _enforce_strict_mode(calls: list[dict], state: dict) -> list[dict]:
    """In strict mode, replace out-of-bounds tool calls with synthetic rejection results."""
    if state.get("plan_mode") != "strict":
        return calls
    current_plan = state.get("current_plan")
    if not current_plan:
        return calls
    steps = current_plan.get("steps", [])
    idx = state.get("plan_step_index", 0)
    if not (0 <= idx < len(steps)):
        return calls
    expected = set(steps[idx].get("expected_tools") or [])
    out = []
    for call in calls:
        if call["name"] in expected:
            out.append(call)
        else:
            out.append({
                **call,
                "_rejected_reason": (
                    f"strict模式：当前步骤只允许 {sorted(expected)} 中的工具，"
                    f"不允许 {call['name']}"
                ),
            })
    return out


def _execute_in_parallel(calls: list[dict], ctx: ToolExecutionContext) -> list[tuple]:
    """Execute parallel-safe tool calls concurrently. Returns [(call, result, ms), ...]."""
    def _run_one(call):
        if call.get("_rejected_reason"):
            from app.chat.runtime.agent_tools.result import error_result
            return call, error_result(call["name"], "strict_violation", call["_rejected_reason"]), 0
        t_tool = time.perf_counter()
        result = execute_tool(call["name"], call["args"], ctx)
        tool_ms = round((time.perf_counter() - t_tool) * 1000)
        return call, result, tool_ms

    with ThreadPoolExecutor(max_workers=min(len(calls), 4)) as pool:
        results = list(pool.map(_run_one, calls))
    return results
