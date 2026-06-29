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
        _attach_step_constraints(plan_dict)
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


def _attach_step_constraints(plan_dict: dict) -> None:
    """Populate per-step constraints so LLM/Vision reflectors actually activate.

    Without this, the Phase 3 LLMReflector/VisionReflector built earlier never
    fire because they're opt-in via step_constraints flags.
    """
    resource_type = plan_dict.get("resource_type", "")
    subject = plan_dict.get("subject", "")
    for step in plan_dict.get("steps", []):
        action = step.get("internal_action", "")
        constraints = dict(step.get("constraints") or {})

        if action == "retrieve_context":
            # Search results: must be relevant + have sources; for教学资源 also need图片
            constraints.setdefault("check_relevance", True)
            constraints.setdefault("require_sources", True)
            constraints.setdefault("min_sources", 1)
            if resource_type in ("ppt", "lesson_plan"):
                constraints.setdefault("require_images", True)
        elif action == "fetch_visuals":
            # image_search step — activate VisionReflector by setting require_images.
            constraints.setdefault("require_images", True)
            constraints.setdefault("min_image_count", 1)
            # Safety net: LLM-driven plan path may forget visual_need; populate
            # query_candidates from the subject so the executor still gets
            # decent search queries.
            visual_need = dict(step.get("visual_need") or {})
            if not visual_need.get("query_candidates"):
                fallback = _build_visual_need(subject, resource_type)
                for key, default in fallback.items():
                    visual_need.setdefault(key, default)
            step["visual_need"] = visual_need
        elif action == "draft_outline":
            constraints.setdefault("check_coherence", True)
            if resource_type == "report":
                constraints.setdefault("min_chapters", 4)
                constraints.setdefault("min_outline_length", 300)
            elif resource_type == "ppt":
                constraints.setdefault("min_chapters", 3)
                constraints.setdefault("min_outline_length", 200)
            elif resource_type == "lesson_plan":
                constraints.setdefault("min_chapters", 3)

        step["constraints"] = constraints


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
    allow_image_search = bool(getattr(capability, "allow_image_search", False))
    disabled = []
    if not allow_rag:
        disabled.append("rag_search（知识库检索未启用）")
    if not allow_web:
        disabled.append("web_search（联网搜索未启用）")
    if not allow_image_search:
        disabled.append("image_search（图片搜索未启用，禁止规划 fetch_visuals 步骤）")
    if disabled:
        context_parts.append(
            "⚠️ 以下工具当前不可用，请勿在 plan 步骤的 expected_tools 中包含它们："
            + "、".join(disabled)
        )
    if allow_image_search and _question_requests_visuals(question):
        context_parts.append(
            "📷 用户明确要求配图/插图，必须在生成步骤之前规划一个 fetch_visuals 步骤"
            "（expected_tools=[\"image_search\"]）来搜集视觉素材。"
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

_VISUAL_KEYWORDS = (
    "配图", "插图", "图片", "示意图", "流程图", "架构图", "结构图",
    "图表", "图解", "配上图", "要图", "带图", "有图",
)

# Query suffixes that orient SearXNG toward technical/教学 imagery rather than
# consumer photos. Style="diagram" in the searxng provider already appends
# "diagram OR flowchart OR architecture", so suffixes here MUST NOT repeat
# those words (doubling pushes results toward icon libraries like devicons).
_DIAGRAM_QUERY_SUFFIXES = (
    "system overview",      # generic, often hits explainer blog posts
    "explained",            # blog/tutorial coverage
    "tutorial",
    "how it works",
    "components",
)


def _question_requests_visuals(question: str) -> bool:
    """Detect whether the user request implies a need for fetched visual assets."""
    if not question:
        return False
    return any(kw in question for kw in _VISUAL_KEYWORDS)


def _extract_english_keywords(subject: str) -> str:
    """Best-effort: keep Latin/digit token runs from the subject. Falls back to
    original subject when nothing usable remains. Helps when subject mixes
    Chinese with English technical terms (e.g. 'RAG 技术' → 'RAG')."""
    import re
    matches = re.findall(r"[A-Za-z][A-Za-z0-9]*", subject or "")
    english = " ".join(m for m in matches if m).strip()
    return english if english else (subject or "").strip()


def _build_visual_query_candidates(subject: str, visual_type: str = "diagram") -> list[str]:
    """Generate query candidates the executor LLM can pick from to call image_search.

    On reflect retry the executor switches to the next unused candidate. The
    first candidate is intentionally the most specific/technical so we hit a
    high-quality educational result on the first try; later candidates broaden.
    """
    base = _extract_english_keywords(subject)
    if not base:
        return []
    candidates: list[str] = []
    seen: set[str] = set()
    for suffix in _DIAGRAM_QUERY_SUFFIXES:
        q = f"{base} {suffix}".strip()
        if q.lower() not in seen:
            candidates.append(q)
            seen.add(q.lower())
        if len(candidates) >= 4:
            break
    return candidates


def _build_visual_need(subject: str, resource_type: str) -> dict:
    """Construct the VisualNeed dict attached to a fetch_visuals plan step.
    Returns plain dict (not the dataclass) for direct embedding in plan_dict."""
    visual_type = "diagram"  # default for教学 content; PPT/lesson_plan rarely want real photos
    return {
        "required": True,
        "type": visual_type,
        "query_candidates": _build_visual_query_candidates(subject, visual_type),
        "purpose": f"为「{subject}」{resource_type or '教学'}内容提供视觉支撑",
        "max_count": 3,
    }


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
    allow_image_search = bool(getattr(capability, "allow_image_search", False))
    needs_visuals = allow_image_search and _question_requests_visuals(question)

    # Confirmation of existing outline → skip to generate
    if state.get("active_draft_outline") and any(kw in question for kw in _CONFIRM_KEYWORDS):
        outline = state["active_draft_outline"]
        rtype = outline.get("resource_type", "report")
        outline_subject = outline.get("subject", subject)
        confirm_steps = []
        if needs_visuals:
            confirm_steps.append({
                "index": 1,
                "user_title": f"为「{outline_subject}」搜集配图",
                "internal_action": "fetch_visuals",
                "expected_tools": ["image_search"],
                "visual_need": _build_visual_need(outline_subject, rtype),
            })
        confirm_steps.append({
            "index": len(confirm_steps) + 1,
            "user_title": f"根据已确认大纲生成{_RTYPE_CN.get(rtype, '内容')}",
            "internal_action": "generate_resource",
            "expected_tools": [f"generate_{rtype}"],
        })
        return {
            "subject": outline_subject,
            "resource_type": rtype,
            "steps": confirm_steps,
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
        if needs_visuals:
            steps.append({
                "index": len(steps) + 1,
                "user_title": f"为{subject}搜集配图",
                "internal_action": "fetch_visuals",
                "expected_tools": ["image_search"],
                "visual_need": _build_visual_need(subject, resource_type),
            })
        steps.append({
            "index": len(steps) + 1,
            "user_title": "展示大纲并等待用户确认",
            "internal_action": "confirm_outline",
            "expected_tools": [],
        })
        steps.append({
            "index": len(steps) + 1,
            "user_title": f"用户确认后生成{type_cn}",
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
