from __future__ import annotations

from langgraph.config import get_config, get_stream_writer

from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.planning.prompts import CREATE_PLAN_SCHEMA, PLANNER_SYSTEM_PROMPT
from app.chat.runtime.planning.schema import Plan, PlanStep


def planner_node(state: AgentState) -> dict:
    writer = get_stream_writer()
    rt = get_config()["configurable"]["runtime"]
    planner_gateway = rt["planner_gateway"]
    request = rt["request"]

    question = str(getattr(request, "question", "") or "")
    replan_hint = state.get("reflect_hint", "")
    existing_plan = state.get("current_plan")

    print(f"[规划器] 开始规划 | 问题=\"{question[:40]}\"  replan={bool(replan_hint)}", flush=True)

    messages = _build_planner_messages(question, state, replan_hint, existing_plan)
    plan_dict = _call_planner_llm(planner_gateway, messages)

    if plan_dict is None:
        plan_dict = _fallback_plan(question, state)
        print("[规划器] LLM未调用工具，使用关键词回退计划", flush=True)

    if plan_dict and plan_dict.get("steps"):
        plan = Plan.from_dict(plan_dict)
        out = plan.to_dict()
        writer({"type": "plan", "payload": out})
        print(f"[规划器] 计划生成 | 步骤数={len(plan.steps)}  主题=\"{plan.subject[:30]}\"", flush=True)
        return {
            "current_plan": out,
            "plan_step_index": 0,
            "plan_mode": "display_only",
            "needs_planning": False,
            "reflect_verdict": "",
            "reflect_hint": "",
        }

    # Planner failed entirely — skip plan, let executor run free
    print("[规划器] 计划生成失败，跳过规划直接执行", flush=True)
    return {"needs_planning": False}


def _build_planner_messages(
    question: str,
    state: dict,
    replan_hint: str,
    existing_plan: dict | None,
) -> list[dict]:
    context_parts = [f"用户请求：{question}"]

    if state.get("active_draft_outline"):
        outline = state["active_draft_outline"]
        context_parts.append(
            f"当前已有大纲：主题={outline.get('subject', '')}，"
            f"类型={outline.get('resource_type', '')}，等待用户确认"
        )

    if existing_plan and replan_hint:
        context_parts.append(f"重规划原因：{replan_hint}")
        context_parts.append("请只修改受影响的步骤，保留已完成的步骤。")

    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(context_parts)},
    ]


def _call_planner_llm(planner_gateway, messages: list[dict]) -> dict | None:
    stream_fn = getattr(planner_gateway, "stream_chat_with_tools", None)
    if not callable(stream_fn):
        return None

    try:
        for event in stream_fn(
            messages,
            [CREATE_PLAN_SCHEMA],
            tool_choice={"type": "function", "function": {"name": "create_plan"}},
            temperature=0.1,
            max_tokens=1024,
        ):
            if event.get("type") == "tool_calls":
                calls = event.get("calls") or []
                if calls and calls[0].get("name") == "create_plan":
                    return calls[0].get("args") or {}
    except Exception as exc:
        print(f"[规划器] LLM调用失败: {exc}", flush=True)

    return None


_RESOURCE_KEYWORDS = {
    "ppt": ("ppt", "PPT", "幻灯片", "课件"),
    "lesson_plan": ("教案", "教学设计", "教学方案"),
    "quiz": ("练习题", "测验", "题目", "习题", "出题"),
    "report": ("报告", "分析报告", "研究报告"),
}

_CONFIRM_KEYWORDS = ("好的", "可以", "确认", "开始", "生成", "ok", "OK", "没问题", "继续", "是的")


def _fallback_plan(question: str, state: dict) -> dict:
    resource_type = "unknown"
    for rtype, kws in _RESOURCE_KEYWORDS.items():
        if any(kw in question for kw in kws):
            resource_type = rtype
            break

    # Infer subject from question
    subject = question[:40].strip()
    for trigger in ("生成", "制作", "写", "创建", "帮我"):
        if trigger in question:
            idx = question.index(trigger) + len(trigger)
            subject = question[idx:].strip()[:40]
            break

    # Confirmation of existing outline → skip to generate
    if state.get("active_draft_outline") and any(kw in question for kw in _CONFIRM_KEYWORDS):
        outline = state["active_draft_outline"]
        rtype = outline.get("resource_type", "report")
        return {
            "subject": outline.get("subject", subject),
            "resource_type": rtype,
            "steps": [
                {
                    "index": 1,
                    "user_title": f"根据已确认大纲生成{_RTYPE_CN.get(rtype, '内容')}",
                    "internal_action": "generate_resource",
                    "expected_tools": [f"generate_{rtype}"],
                }
            ],
        }

    if resource_type == "quiz":
        steps = [
            {
                "index": 1,
                "user_title": f"生成{subject}练习题",
                "internal_action": "generate_resource",
                "expected_tools": ["generate_quiz"],
            }
        ]
    elif resource_type in ("report", "ppt", "lesson_plan"):
        type_cn = _RTYPE_CN.get(resource_type, "内容")
        tool_name = f"generate_{resource_type}"
        steps = [
            {
                "index": 1,
                "user_title": f"起草{subject}{type_cn}大纲",
                "internal_action": "draft_outline",
                "expected_tools": ["draft_outline"],
            },
            {
                "index": 2,
                "user_title": "检索相关资料",
                "internal_action": "retrieve_context",
                "expected_tools": ["rag_search", "web_search"],
            },
            {
                "index": 3,
                "user_title": f"确认大纲后生成{type_cn}",
                "internal_action": "generate_resource",
                "expected_tools": [tool_name],
            },
        ]
    else:
        return {}

    return {"subject": subject, "resource_type": resource_type, "steps": steps}


_RTYPE_CN = {
    "report":      "报告",
    "ppt":         "PPT课件",
    "lesson_plan": "教案",
    "quiz":        "练习题",
}
