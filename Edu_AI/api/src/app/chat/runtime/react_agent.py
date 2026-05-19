"""P4-A ReAct Agent — full conversation orchestration.

Public API: ReActAgent.run_stream(*, request, snapshot) -> Iterator[dict]

SSE event sequence:
  {type: "status",       payload: {stage: "thinking", label: "..."}}
  {type: "delta",        payload: {content: "..."}}         <- streaming text
  {type: "tool_call",    payload: {tool: str, args: dict}}
  {type: "tool_result",  payload: {tool: str, summary: str, ok: bool}}
  {type: "task_submitted", payload: {task_id: str, workflow_type: str, message: str}}
  {type: "result",       payload: {...}}                     <- final result (compatible with existing format)
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterator

from core.config import Config
from app.chat.runtime.agent_tools import (
    ToolExecutionContext,
    build_tool_schemas,
    execute_tool,
)
from app.chat.runtime.agent_tools.constants import TOOL_TO_WORKFLOW

AGENT_SYSTEM_PROMPT = """你是一个教学资源助手，帮助用户生成报告、PPT、教案和练习题。

【信息收集原则】
- 如果缺少必要信息（主题/课题），先通过自然对话追问，不要调用任何工具
- 一次最多问 2 个问题，不要列清单式追问

【大纲确认流程】（报告/PPT/教案需要，练习题不需要）
1. 信息充足后，调用 draft_outline 工具生成大纲
2. 将大纲内容展示给用户，询问是否需要调整
3. 用户确认后（说"可以"/"好"/"开始"等），调用对应 generate_* 工具，传入 confirmed_outline

【工具调用原则】
- generate_* 工具只在用户明确确认大纲后调用，必须传入 confirmed_outline 参数
- generate_quiz 无大纲步骤，用户明确要求时直接调用
- 调用 generate_* 后，告知用户任务已在后台处理
- 普通问答直接回答，不调用任何工具

【语气要求】
- 自然、简洁，避免"请输入'确认并继续'"等命令式提示
- 追问时不超过 2 个问题"""

_WORKFLOW_LABELS = {
    "report":      "报告",
    "ppt":         "PPT课件",
    "lesson_plan": "教案",
    "quiz":        "练习题",
}


class _AgentTimeout(Exception):
    pass


class ReActAgent:
    def __init__(
        self,
        *,
        agent_gateway,
        fast_runtime,
        rag_retriever=None,
        web_retriever=None,
        workflow_registry=None,
        background_runner=None,
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ):
        self.agent_gateway = agent_gateway
        self.fast_runtime = fast_runtime
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.workflow_registry = workflow_registry or {}
        self.background_runner = background_runner
        self.max_steps = max_steps if max_steps is not None else Config.REACT_MAX_STEPS
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else Config.REACT_TIMEOUT_SECONDS

    def run_stream(self, *, request, snapshot) -> Iterator[dict]:
        t_start = time.perf_counter()
        trace_id = str(uuid.uuid4())
        capability = getattr(snapshot, "capability", None)

        yield {"type": "status", "payload": {"stage": "thinking", "label": "正在分析请求..."}}

        tool_schemas = build_tool_schemas(capability)
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

        messages = self._build_messages(request, snapshot)

        try:
            yield from self._react_loop(messages, tool_schemas, ctx, request, snapshot, t_start)
        except _AgentTimeout:
            print(f"[AGENT] 超时 fallback trace_id={trace_id}", flush=True)
            yield from self._fallback(request, snapshot, reason="react_timeout")
        except Exception as exc:
            print(f"[AGENT] 异常 fallback trace_id={trace_id} exc={exc}", flush=True)
            yield from self._fallback(request, snapshot, reason=f"react_error: {exc}")

    def _react_loop(
        self,
        messages: list,
        tool_schemas: list,
        ctx: ToolExecutionContext,
        request,
        snapshot,
        t_start: float,
    ) -> Iterator[dict]:
        stream_fn = getattr(self.agent_gateway, "stream_chat_with_tools", None)
        if not callable(stream_fn):
            yield from self._fallback(request, snapshot, reason="gateway_no_tools_support")
            return

        answer_chunks: list[str] = []
        task_submitted_events: list[dict] = []

        while True:
            if (time.perf_counter() - t_start) > self.timeout_seconds:
                raise _AgentTimeout()

            events = list(stream_fn(
                messages,
                tool_schemas,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1024,
            ))

            if any(e["type"] == "unsupported" for e in events):
                yield from self._fallback(request, snapshot, reason="unsupported_function_calling")
                return

            if any(e["type"] == "error" for e in events):
                err_msg = next((e["message"] for e in events if e["type"] == "error"), "未知错误")
                yield from self._fallback(request, snapshot, reason=f"llm_error: {err_msg}")
                return

            tool_calls_event = None
            for e in events:
                if e["type"] == "text_delta":
                    answer_chunks.append(e["content"])
                    yield {"type": "delta", "payload": {"content": e["content"]}}
                elif e["type"] == "tool_calls":
                    tool_calls_event = e

            if tool_calls_event is None:
                break

            tool_results_for_messages = []
            for call in tool_calls_event["calls"]:
                tool_name = call["name"]
                tool_args = call["args"]
                call_id = call.get("id") or f"call_{tool_name}"

                yield {"type": "tool_call", "payload": {"tool": tool_name, "args": tool_args}}

                result = execute_tool(tool_name, tool_args, ctx)

                yield {"type": "tool_result", "payload": {
                    "tool": tool_name,
                    "summary": result.get("summary", ""),
                    "ok": result.get("ok", False),
                }}

                if result.get("ok") and tool_name in TOOL_TO_WORKFLOW:
                    payload = result.get("payload", {})
                    task_id = payload.get("task_id", "")
                    workflow_type = payload.get("workflow_type", "")
                    if task_id:
                        label = _WORKFLOW_LABELS.get(workflow_type, "内容")
                        task_submitted_events.append({
                            "type": "task_submitted",
                            "payload": {
                                "task_id": task_id,
                                "workflow_type": workflow_type,
                                "message": f"正在后台生成{label}，可通过任务ID查询进度",
                            },
                        })

                tool_result_content = _format_tool_result_for_context(tool_name, result)
                tool_results_for_messages.append({
                    "tool_call_id": call_id,
                    "role": "tool",
                    "name": tool_name,
                    "content": tool_result_content,
                })

            messages = messages + [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": c.get("id") or f"call_{c['name']}",
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c["args"], ensure_ascii=False),
                            },
                        }
                        for c in tool_calls_event["calls"]
                    ],
                },
                *tool_results_for_messages,
            ]

        for evt in task_submitted_events:
            yield evt

        total_ms = round((time.perf_counter() - t_start) * 1000)
        ctx.trace["total_ms"] = total_ms
        answer = "".join(answer_chunks)
        yield {
            "type": "result",
            "payload": {
                "message": {"role": "assistant", "content": answer},
                "conversation": {"conversation_id": getattr(request, "conversation_id", "") or ""},
                "action": {"name": "agent.reply"},
                "artifacts": [],
                "workflow": None,
                "sources": [],
                "trace": ctx.trace,
            },
        }

    def _build_messages(self, request, snapshot) -> list[dict]:
        recent = list(getattr(snapshot, "recent_messages", []) or [])
        history = []
        for msg in recent:
            role = str((msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "user")) or "user")
            content = str((msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")) or "")
            if content:
                history.append({"role": role, "content": content})
        return [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": str(getattr(request, "question", "") or "")},
        ]

    def _fallback(self, request, snapshot, *, reason: str) -> Iterator[dict]:
        print(f"[AGENT] fallback reason={reason}", flush=True)
        yield {"type": "status", "payload": {"stage": "fallback", "label": "切换到直接回答模式"}}
        from app.chat.domain.route_decision import RouteDecision
        decision = RouteDecision.fast(action="chat.reply", reason=reason)
        yield from self.fast_runtime.run_stream(request=request, snapshot=snapshot, decision=decision)


def _format_tool_result_for_context(tool_name: str, result: dict) -> str:
    if not result.get("ok"):
        return f"工具 {tool_name} 执行失败: {result.get('error', '未知错误')}"
    payload = result.get("payload", {})
    if tool_name == "rag_search":
        return f"知识库检索结果：\n{payload.get('answer', '无内容')}"
    if tool_name == "web_search":
        return f"联网检索结果：\n{payload.get('summary', '无内容')}"
    if tool_name == "draft_outline":
        return f"已生成大纲：\n{payload.get('outline_markdown', '')}"
    if tool_name in TOOL_TO_WORKFLOW:
        return f"已提交后台任务，task_id={payload.get('task_id', '')}"
    return result.get("summary", "")
