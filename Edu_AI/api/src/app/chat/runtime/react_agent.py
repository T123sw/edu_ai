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

AGENT_SYSTEM_PROMPT = """你是一个教学资源助手，帮助教师生成报告、PPT课件、教案和练习题。

【自主规划原则】
接到生成任务后，自主规划完整执行路径并逐步执行，无需用户介入中间步骤。
每次工具返回后，先评估结果质量，再决定下一步行动。

【资源生成标准执行路径】（报告 / PPT / 教案）
第1步 → draft_outline：起草结构化大纲
第2步 → rag_search：检索知识库，获取相关内容和配图素材
第3步 → （若知识库内容不足）web_search：补充联网资料
第4步 → 向用户完整展示大纲，附上检索到的关键材料，询问是否满意或需要调整
第5步 → 用户确认后：调用对应 generate_* 工具，传入 confirmed_outline 参数

【练习题路径】直接调用 generate_quiz，无需大纲步骤。
【普通问答/闲聊】直接回答，不调用任何工具。

【每步自检规则】
- rag_search 返回内容为空或过少 → 改用 web_search 重试
- draft_outline 内容过短（少于200字）→ 重新调用并增大篇幅要求
- 检索内容缺少图片/图表 → 额外调用 web_search 搜索"主题+图表"
- generate_* 提交失败 → 说明原因，询问用户是否重试

【用户确认识别】
若历史对话中已展示过大纲，且用户当前回复表示满意/确认/好的/OK，
则从历史中提取大纲原文作为 confirmed_outline，直接调用对应 generate_* 工具。

【追问规则】
主题完全不清楚时才追问，一次最多问 2 个问题。
主题已知时直接执行第1步，不要多余追问。

【语气】自然简洁，不使用命令式表达。"""

_WORKFLOW_LABELS = {
    "report":      "报告",
    "ppt":         "PPT课件",
    "lesson_plan": "教案",
    "quiz":        "练习题",
}

_TOOL_NAMES_CN = {
    "rag_search":           "知识库检索",
    "web_search":           "联网搜索",
    "draft_outline":        "起草大纲",
    "generate_report":      "生成报告",
    "generate_ppt":         "生成PPT",
    "generate_lesson_plan": "生成教案",
    "generate_quiz":        "生成练习题",
}

_ARG_KEYS_CN = {
    "subject":           "主题",
    "topic":             "主题",
    "query":             "查询",
    "confirmed_outline": "大纲",
    "focus":             "侧重",
    "grade":             "年级",
    "difficulty":        "难度",
    "question_count":    "题数",
    "slide_count":       "页数",
    "duration_minutes":  "时长",
    "question_types":    "题型",
    "outline_type":      "类型",
}

# 工具结果观察提示：引导模型评估质量并决定下一步
_OBSERVE_HINTS = {
    "rag_search": (
        "\n\n【自检】请评估以上检索结果："
        "内容是否充分？是否有图片/图表？若不足，继续调用 web_search 补充。"
    ),
    "web_search": (
        "\n\n【自检】请评估以上联网结果是否满足需求。"
        "若已充分，进行下一步。"
    ),
    "draft_outline": "",  # draft_outline 的提示由 _format_tool_result_for_context 单独处理
}


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
            key_cn = _ARG_KEYS_CN.get(k, k)
            parts.append(f"{key_cn}={v_str!r}")
    return "  ".join(parts)


class _AgentTimeout(Exception):
    pass


class ReActAgent:
    def __init__(
        self,
        *,
        agent_gateway,
        fast_runtime,
        planner_gateway=None,   # 保留参数兼容性，不再使用
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

        username = str(getattr(request, "owner", "") or "匿名")
        question = str(getattr(request, "question", "") or "")
        print(f"[智能体] 开始   | 用户={username}  问题=\"{question[:40]}\"", flush=True)

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
            print(f"[智能体] 超时   | 已触发降级", flush=True)
            yield from self._fallback(request, snapshot, reason="react_timeout")
        except Exception as exc:
            print(f"[智能体] 异常   | {exc}", flush=True)
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
        step = 0

        while True:
            if (time.perf_counter() - t_start) > self.timeout_seconds:
                raise _AgentTimeout()

            step += 1
            t_llm = time.perf_counter()
            t_first: float | None = None
            tool_calls_event = None
            should_fallback: tuple | None = None  # (reason,)

            # 改动 A：真正流式，text_delta 立即 yield，不再 list() 阻塞
            for e in stream_fn(
                messages,
                tool_schemas,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=2048,   # 改动 E：1024 → 2048，避免大纲截断
            ):
                etype = e["type"]
                if etype == "text_delta":
                    if t_first is None:
                        t_first = time.perf_counter()
                        print(f"[智能体] 第{step}轮   | ttft {(t_first - t_llm)*1000:.0f}ms", flush=True)
                    answer_chunks.append(e["content"])
                    yield {"type": "delta", "payload": {"content": e["content"]}}
                elif etype == "tool_calls":
                    tool_calls_event = e
                elif etype == "error":
                    should_fallback = (f"llm_error: {e['message']}",)
                    break
                elif etype == "unsupported":
                    should_fallback = ("unsupported_function_calling",)
                    break
                # "done" → 内层循环自然结束

            if should_fallback:
                yield from self._fallback(request, snapshot, reason=should_fallback[0])
                return

            llm_ms = round((time.perf_counter() - t_llm) * 1000)
            if tool_calls_event is not None:
                tool_names_cn = [_TOOL_NAMES_CN.get(c["name"], c["name"]) for c in tool_calls_event["calls"]]
                print(f"[智能体] 第{step}轮   | {llm_ms}ms  调用工具: {'、'.join(tool_names_cn)}", flush=True)
            else:
                print(f"[智能体] 第{step}轮   | {llm_ms}ms  直接回答", flush=True)

            if tool_calls_event is None:
                break

            tool_results_for_messages = []
            for call in tool_calls_event["calls"]:
                tool_name = call["name"]
                tool_args = call["args"]
                call_id = call.get("id") or f"call_{tool_name}"

                print(f"[智能体] 调用    | {_TOOL_NAMES_CN.get(tool_name, tool_name)}  {_fmt_tool_args(tool_args)}", flush=True)
                yield {"type": "tool_call", "payload": {"tool": tool_name, "args": tool_args}}

                t_tool = time.perf_counter()
                result = execute_tool(tool_name, tool_args, ctx)
                tool_ms = round((time.perf_counter() - t_tool) * 1000)

                ok_label = "成功" if result.get("ok") else "失败"
                summary = str(result.get("summary", ""))[:40]
                _pl = result.get("payload") or {}
                _tid = str(_pl.get("task_id") or "") if isinstance(_pl, dict) else ""
                task_hint = f"  任务={_tid[:10]}" if _tid else ""
                print(f"[智能体] 结果    | {ok_label}  {summary}  {tool_ms}ms{task_hint}", flush=True)

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
                        yield {
                            "type": "task_submitted",
                            "payload": {
                                "task_id": task_id,
                                "workflow_type": workflow_type,
                                "message": f"正在后台生成{label}，可通过任务ID查询进度",
                            },
                        }

                tool_results_for_messages.append({
                    "tool_call_id": call_id,
                    "role": "tool",
                    "content": _format_tool_result_for_context(tool_name, result),
                })

            messages = messages + [
                {
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
                        for c in tool_calls_event["calls"]
                    ],
                },
                *tool_results_for_messages,
            ]

        total_ms = round((time.perf_counter() - t_start) * 1000)
        ctx.trace["total_ms"] = total_ms
        answer = "".join(answer_chunks)
        print(f"[智能体] 完成    | 共{step}轮  工具{ctx.step_count}次  回答={len(answer)}字  总耗时={total_ms}ms", flush=True)
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
        """构建消息列表，完整保留历史（含 tool_calls 轮次）。"""
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

            # 改动 B：保留工具调用轮次，让 agent 知道上轮做了什么
            if role == "assistant" and tool_calls:
                history.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            elif role == "tool" and tool_call_id:
                history.append({"role": "tool", "tool_call_id": tool_call_id, "content": content_str})
            elif content_str:
                history.append({"role": role, "content": content_str})

        return [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": str(getattr(request, "question", "") or "")},
        ]

    def _fallback(self, request, snapshot, *, reason: str) -> Iterator[dict]:
        print(f"[智能体] 降级   | 原因={reason}", flush=True)
        yield {"type": "status", "payload": {"stage": "fallback", "label": "切换到直接回答模式"}}
        from app.chat.domain.route_decision import RouteDecision
        decision = RouteDecision.fast(action="chat.reply", reason=reason)
        yield from self.fast_runtime.run_stream(request=request, snapshot=snapshot, decision=decision)


def _format_tool_result_for_context(tool_name: str, result: dict) -> str:
    """格式化工具结果，附加自检观察提示（改动 D）。"""
    if not result.get("ok"):
        return f"工具 {tool_name} 执行失败: {result.get('error', '未知错误')}"

    payload = result.get("payload", {})

    if tool_name == "rag_search":
        content = f"知识库检索结果：\n{payload.get('answer', '无内容')}"
        return content + _OBSERVE_HINTS["rag_search"]

    if tool_name == "web_search":
        content = f"联网检索结果：\n{payload.get('summary', '无内容')}"
        return content + _OBSERVE_HINTS["web_search"]

    if tool_name == "draft_outline":
        outline = payload.get("outline_markdown", "")
        return (
            f"大纲已生成，请在回复中将以下大纲内容**完整逐字输出**给用户，"
            f"然后说明你接下来会检索相关材料，不要省略大纲正文：\n\n{outline}"
        )

    if tool_name in TOOL_TO_WORKFLOW:
        return f"已提交后台任务，task_id={payload.get('task_id', '')}"

    return result.get("summary", "")
