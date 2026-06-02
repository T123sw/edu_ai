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
    capability = rt.get("capability")

    question = str(getattr(request, "question", "") or "")
    replan_hint = state.get("reflect_hint", "")
    existing_plan = state.get("current_plan")

    print(f"[规划器] 开始规划 | 问题=\"{question[:40]}\"  replan={bool(replan_hint)}", flush=True)

    messages = _build_planner_messages(question, state, replan_hint, existing_plan, capability)
    plan_dict = _call_planner_llm(planner_gateway, messages)

    if plan_dict is None:
        plan_dict = _fallback_plan(question, state, capability)
        print("[规划器] LLM未调用工具，使用关键词回退计划", flush=True)

    if plan_dict and plan_dict.get("steps"):
        plan = Plan.from_dict(plan_dict)
        out = plan.to_dict()
        writer({"type": "plan", "payload": out})
        print(f"[规划器] 计划生成 | 步骤数={len(plan.steps)}  主题=\"{plan.subject[:30]}\"", flush=True)
        return {
            "current_plan": out,
            "plan_step_index": 0,
            "plan_mode": "guided",   # Phase 3: executor follows plan steps
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
    capability=None,
) -> list[dict]:
    context_parts = [f"用户请求：{question}"]

    # Capability constraints — planner must not propose tools the runtime won't allow.
    allow_rag = bool(getattr(capability, "allow_rag", False))
    allow_web = bool(getattr(capability, "allow_web", False))
    disabled = []
    if not allow_rag:
        disabled.append("rag_search（知识库检索未启用）")
    if not allow_web:
        disabled.append("web_search（联网搜索未启用）")
    if disabled:
        context_parts.append(
            "⚠️ 以下工具当前不可用，请勿在 plan 步骤的 expected_tools 中包含它们："
            + "、".join(disabled)
        )

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
    """Call the planner LLM with tool_choice='auto'.

    Note: forced tool_choice={"function": "create_plan"} is silently ignored by
    Qwen / 通义 models — they return zero events instead of calling the tool.
    Using "auto" plus a strong system prompt ("调用 create_plan 工具返回计划")
    works reliably across Qwen / DeepSeek / OpenAI.
    """
    stream_fn = getattr(planner_gateway, "stream_chat_with_tools", None)
    if not callable(stream_fn):
        return None

    try:
        for event in stream_fn(
            messages,
            [CREATE_PLAN_SCHEMA],
            tool_choice="auto",
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


def _extract_subject(question: str) -> str:
    """Strip prefixes / trailing constraints to get a clean topic phrase."""
    import re

    s = question
    # 1) strip leading verbs (帮我/给我/请/能否…)
    for prefix in ("帮我", "给我", "请帮", "请", "能否", "可以", "能不能"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    # 2) strip action verbs
    for verb in ("生成", "制作", "写一份", "写一个", "写", "创建", "做一份", "做一个", "做", "出"):
        if s.startswith(verb):
            s = s[len(verb):]
            break
    # 3) strip leading quantifiers (一份/一个/一篇/几道…)
    s = re.sub(r"^(一[份个篇张本套节])", "", s)
    s = re.sub(r"^\d+\s*[道个张份只篇章节题课]", "", s)
    # 4) strip trailing constraint clauses (after comma/Chinese comma)
    s = re.split(r"[，,]", s, maxsplit=1)[0]
    # 5) strip trailing word-count / page-count specs
    s = re.sub(r"\d+\s*(字|页|张|道题?|分钟|min|words?)\s*$", "", s, flags=re.IGNORECASE)
    # 6) strip trailing resource-type noise (报告/PPT/教案/练习题)
    s = re.sub(r"(报告|分析报告|研究报告|综述报告|PPT课件|PPT|课件|教案|教学设计|教学方案|练习题|测验|题目|习题)\s*$", "", s, flags=re.IGNORECASE)

    s = s.strip(" .。、,，:：;；")
    return s[:40] if s else question[:40].strip()


def _fallback_plan(question: str, state: dict, capability=None) -> dict:
    resource_type = "unknown"
    for rtype, kws in _RESOURCE_KEYWORDS.items():
        if any(kw in question for kw in kws):
            resource_type = rtype
            break

    subject = _extract_subject(question)
    allow_rag = bool(getattr(capability, "allow_rag", False))
    allow_web = bool(getattr(capability, "allow_web", False))

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
            }
        ]
        # Only include retrieval step when at least one retrieval tool is allowed
        retrieve_tools = [t for t, ok in (("rag_search", allow_rag), ("web_search", allow_web)) if ok]
        if retrieve_tools:
            steps.append({
                "index": len(steps) + 1,
                "user_title": "检索相关资料",
                "internal_action": "retrieve_context",
                "expected_tools": retrieve_tools,
            })
        steps.append({
            "index": len(steps) + 1,
            "user_title": f"确认大纲后生成{type_cn}",
            "internal_action": "generate_resource",
            "expected_tools": [tool_name],
        })
    else:
        return {}

    return {"subject": subject, "resource_type": resource_type, "steps": steps}


_RTYPE_CN = {
    "report":      "报告",
    "ppt":         "PPT课件",
    "lesson_plan": "教案",
    "quiz":        "练习题",
}
