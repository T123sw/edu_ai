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

AGENT_SYSTEM_PROMPT = """你是一个教学资源助手，专门帮助教师生成报告、PPT课件、教案和练习题。

【意图识别与工具决策】
根据用户请求，按以下规则决定行动：

▸ 用户要生成 报告/研究报告/总结 → 调用 draft_outline(resource_type=report)
▸ 用户要生成 PPT/幻灯片/课件   → 调用 draft_outline(resource_type=ppt)
▸ 用户要生成 教案/课程设计      → 调用 draft_outline(resource_type=lesson_plan)
▸ 用户要生成 练习题/习题/试题   → 直接调用 generate_quiz（不需要大纲步骤）
▸ 普通问答/概念解释/闲聊        → 直接回答，不调用任何工具

【资源生成标准流程】（报告 / PPT / 教案）
第一步：主题明确时，立即调用 draft_outline 生成大纲，不要先问用户
第二步：将大纲展示给用户，用一句话询问是否满意或需要调整
第三步：用户确认后，调用对应 generate_* 工具，并传入 confirmed_outline 参数
第四步：告知用户任务已在后台处理

【追问规则】
只有主题完全不清楚时才追问，且一次最多问 2 个问题。
主题已知时，直接进入大纲生成阶段，不要多余追问。

【语气】自然简洁，不使用"请输入确认"等命令式表达。"""

_PLANNER_SYSTEM_PROMPT = """你是一个任务分解助手。将用户的任务拆解为有序执行步骤（2-4步）。

输出格式（每行一个步骤）：
步骤1: <具体操作>
步骤2: <具体操作>
...

规则：
- 资源生成类任务（报告/PPT/教案）：步骤固定为 起草大纲 → 用户确认 → 生成内容
- 练习题：只需 生成练习题
- 普通问答/闲聊：只输出"直接回答"
- 不要输出步骤以外的任何说明文字"""

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
    "subject":          "主题",
    "topic":            "主题",
    "query":            "查询",
    "confirmed_outline":"大纲",
    "focus":            "侧重",
    "grade":            "年级",
    "difficulty":       "难度",
    "question_count":   "题数",
    "slide_count":      "页数",
    "duration_minutes": "时长",
    "question_types":   "题型",
    "outline_type":     "类型",
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
        planner_gateway=None,
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
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever
        self.workflow_registry = workflow_registry or {}
        self.background_runner = background_runner
        self.max_steps = max_steps if max_steps is not None else Config.REACT_MAX_STEPS
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else Config.REACT_TIMEOUT_SECONDS

    def _plan_task(self, question: str) -> list[str]:
        """调用快速模型对任务做分解，返回有序步骤列表；普通问答返回空列表。"""
        if not question.strip():
            return []
        try:
            t0 = time.perf_counter()
            gateway = self.planner_gateway or getattr(self.fast_runtime, "model_gateway", None)
            if gateway is None:
                return []
            raw = gateway.chat(
                [
                    {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                temperature=0.1,
                max_tokens=120,
            )
            plan_ms = round((time.perf_counter() - t0) * 1000)
            lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
            if not lines or lines[0] == "直接回答":
                print(f"[智能体] 规划   | 普通问答，跳过工具  {plan_ms}ms", flush=True)
                return []
            for line in lines:
                print(f"[智能体] 规划   | {line}", flush=True)
            print(f"[智能体] 规划   | 共{len(lines)}步  {plan_ms}ms", flush=True)
            return lines
        except Exception as exc:
            print(f"[智能体] 规划   | 分解失败，继续执行  {exc}", flush=True)
            return []

    def run_stream(self, *, request, snapshot) -> Iterator[dict]:
        t_start = time.perf_counter()
        trace_id = str(uuid.uuid4())
        capability = getattr(snapshot, "capability", None)

        username = str(getattr(request, "owner", "") or "匿名")
        question = str(getattr(request, "question", "") or "")
        q_preview = question[:40]
        print(f"[智能体] 开始   | 用户={username}  问题=\"{q_preview}\"", flush=True)

        yield {"type": "status", "payload": {"stage": "thinking", "label": "正在分析请求..."}}

        # 规划阶段：分解任务
        plan_steps = self._plan_task(question)
        if plan_steps:
            yield {
                "type": "status",
                "payload": {
                    "stage": "planning",
                    "label": f"任务已分解为{len(plan_steps)}个步骤",
                    "steps": plan_steps,
                },
            }

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

        messages = self._build_messages(request, snapshot, plan_steps=plan_steps)

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

            events = list(stream_fn(
                messages,
                tool_schemas,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1024,
            ))

            llm_ms = round((time.perf_counter() - t_llm) * 1000)

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

                tool_name_cn = _TOOL_NAMES_CN.get(tool_name, tool_name)
                print(f"[智能体] 调用    | {tool_name_cn}  {_fmt_tool_args(tool_args)}", flush=True)

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

                tool_result_content = _format_tool_result_for_context(tool_name, result)
                tool_results_for_messages.append({
                    "tool_call_id": call_id,
                    "role": "tool",
                    "content": tool_result_content,
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

    def _build_messages(self, request, snapshot, *, plan_steps: list[str] = ()) -> list[dict]:
        recent = list(getattr(snapshot, "recent_messages", []) or [])
        history = []
        for msg in recent:
            role = str((msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "user")) or "user")
            content = str((msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")) or "")
            if content:
                history.append({"role": role, "content": content})

        system_content = AGENT_SYSTEM_PROMPT
        if plan_steps:
            plan_text = "\n".join(plan_steps)
            system_content += (
                f"\n\n【本次任务分解计划】\n{plan_text}\n"
                "请严格按此计划逐步执行，当前执行第一步。"
            )

        return [
            {"role": "system", "content": system_content},
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
    if not result.get("ok"):
        return f"工具 {tool_name} 执行失败: {result.get('error', '未知错误')}"
    payload = result.get("payload", {})
    if tool_name == "rag_search":
        return f"知识库检索结果：\n{payload.get('answer', '无内容')}"
    if tool_name == "web_search":
        return f"联网检索结果：\n{payload.get('summary', '无内容')}"
    if tool_name == "draft_outline":
        outline = payload.get('outline_markdown', '')
        return (
            f"大纲已生成，请在回复中将以下大纲内容**完整逐字输出**给用户，"
            f"然后用一句话询问是否满意或需要调整，不要省略或摘要大纲正文：\n\n{outline}"
        )
    if tool_name in TOOL_TO_WORKFLOW:
        return f"已提交后台任务，task_id={payload.get('task_id', '')}"
    return result.get("summary", "")
