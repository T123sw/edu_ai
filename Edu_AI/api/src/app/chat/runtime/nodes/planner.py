from __future__ import annotations

from langgraph.config import get_config, get_stream_writer

from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.planning.compiler import compile_plan
from app.chat.runtime.planning.prompts import CREATE_PLAN_SCHEMA, PLANNER_SYSTEM_PROMPT
from app.chat.runtime.planning.schema import Plan, PlanStep
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract
from app.chat.runtime.execution.idempotency import ensure_logical_task_id


def planner_node(state: AgentState) -> dict:
    writer = get_stream_writer()
    rt = get_config()["configurable"]["runtime"]
    planner_gateway = rt["planner_gateway"]
    request = rt["request"]
    capability = rt.get("capability")

    question = str(getattr(request, "question", "") or "")
    # The model may later enrich non-execution language, but workflow authority
    # belongs to this deterministic contract + compiler pair.  It prevents an
    # invalid model plan from being "fixed" by several competing post-processors.
    contract = extract_task_contract(
        request,
        capability,
        state,
        snapshot=rt.get("snapshot"),
    )
    ctx = rt.get("ctx")
    if ctx is not None:
        ctx.task_contract = contract.model_dump(mode="json")
        if state.get("logical_task_id"):
            ctx.logical_task_id = state["logical_task_id"]
        ensure_logical_task_id(ctx)
    plan = compile_plan(contract, state)
    out = plan.to_dict()
    writer({"type": "plan", "payload": out})
    print(
        f"[规划器] 编译计划 | intent={contract.intent} template={plan.template_id} "
        f"steps={len(plan.steps)} topic=\"{plan.subject[:30]}\"",
        flush=True,
    )
    return {
        "current_plan": out,
        "plan_step_index": 0,
        "plan_mode": "strict",
        "needs_planning": False,
        "reflect_verdict": "",
        "reflect_hint": "",
        "task_contract": contract.model_dump(mode="json"),
        "logical_task_id": getattr(ctx, "logical_task_id", "") if ctx is not None else "",
    }


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


def _ensure_mandatory_retrieval_when_enabled(plan_dict: dict, capability) -> None:
    """Ensure generated plans cannot omit retrieval enabled by the user."""
    required_tools = [
        tool_name
        for tool_name, enabled in (
            ("rag_search", bool(getattr(capability, "allow_rag", False))),
            ("web_search", bool(getattr(capability, "allow_web", False))),
        )
        if enabled
    ]
    if not required_tools:
        return

    steps = plan_dict.get("steps") or []
    retrieval_step = next(
        (
            step
            for step in steps
            if step.get("internal_action") == "retrieve_context"
            or any(
                tool_name in (step.get("expected_tools") or [])
                for tool_name in ("rag_search", "web_search")
            )
        ),
        None,
    )
    if retrieval_step is not None:
        expected_tools = list(retrieval_step.get("expected_tools") or [])
        duplicate_retrieval_steps = [
            step
            for step in steps
            if step is not retrieval_step
            and (
                step.get("internal_action") == "retrieve_context"
                or any(
                    tool_name in (step.get("expected_tools") or [])
                    for tool_name in ("rag_search", "web_search")
                )
            )
        ]
        for duplicate in duplicate_retrieval_steps:
            for tool_name in duplicate.get("expected_tools") or []:
                if tool_name in ("rag_search", "web_search") and tool_name not in expected_tools:
                    expected_tools.append(tool_name)
        if duplicate_retrieval_steps:
            steps[:] = [step for step in steps if step not in duplicate_retrieval_steps]
        for tool_name in required_tools:
            if tool_name not in expected_tools:
                expected_tools.append(tool_name)
        retrieval_step["expected_tools"] = expected_tools
        retrieval_step["internal_action"] = "retrieve_context"
        retrieval_index = steps.index(retrieval_step)
        if retrieval_index > 0:
            steps.pop(retrieval_index)
            steps.insert(0, retrieval_step)
    else:
        steps.insert(
            0,
            {
                "index": 1,
                "user_title": "检索已启用的资料来源",
                "internal_action": "retrieve_context",
                "expected_tools": required_tools,
            },
        )

    for index, step in enumerate(steps, start=1):
        step["index"] = index
    plan_dict["steps"] = steps


def _ensure_outline_confirmation_boundary(plan_dict: dict, state: dict) -> None:
    """Do not let an initial outline workflow submit a resource in one turn.

    Models occasionally omit ``confirm_outline`` or continue past it.  Report,
    PPT and lesson-plan generation are irreversible background submissions, so
    the initial turn must end at confirmation.  A later turn that starts with a
    persisted outline is the only turn allowed to plan ``generate_resource``.
    """
    if plan_dict.get("resource_type") not in {"report", "ppt", "lesson_plan"}:
        return
    if state.get("active_draft_outline"):
        return
    steps = [
        step
        for step in list(plan_dict.get("steps") or [])
        if step.get("internal_action") not in {"generate_resource", "fetch_visuals"}
        and not any(
            str(tool).startswith("generate_")
            for tool in list(step.get("expected_tools") or [])
        )
    ]
    if not any(step.get("internal_action") == "draft_outline" for step in steps):
        steps.insert(
            0,
            {
                "index": 1,
                "user_title": "起草资源大纲",
                "internal_action": "draft_outline",
                "expected_tools": ["draft_outline"],
            },
        )
    steps = [
        step for step in steps if step.get("internal_action") != "confirm_outline"
    ]
    steps.append(
        {
            "index": len(steps) + 1,
            "user_title": "展示大纲并等待用户确认",
            "internal_action": "confirm_outline",
            "expected_tools": [],
        }
    )
    for index, step in enumerate(steps, start=1):
        step["index"] = index
    plan_dict["steps"] = steps


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
    "blog": ("教学博客", "博客", "博文"),
    "flashcard": ("闪卡", "复习卡", "记忆卡"),
    "graph": ("思维导图", "导图", "知识图谱"),
    "game": ("课堂小游戏", "小游戏", "教学游戏"),
    "classroom": ("AI课堂", "AI 课堂", "智能课堂", "互动课堂"),
    "report": ("报告", "分析报告", "研究报告"),
}


def _explicit_resource_type(question: str) -> str:
    for resource_type, keywords in _RESOURCE_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return resource_type
    return "unknown"


def _enforce_explicit_resource_type(plan_dict: dict, question: str) -> None:
    """User-named resource types outrank probabilistic planner classification."""
    resource_type = _explicit_resource_type(question)
    if resource_type == "unknown":
        return
    plan_dict["resource_type"] = resource_type
    if resource_type not in {"quiz", "blog", "flashcard", "graph", "game", "classroom"}:
        return
    subject = str(plan_dict.get("subject") or _extract_subject(question)).strip()
    plan_dict["subject"] = subject
    plan_dict["steps"] = [
        {
            "index": 1,
            "user_title": f"生成{subject}{_RTYPE_CN.get(resource_type, '资源')}",
            "internal_action": "generate_resource",
            "expected_tools": [f"generate_{resource_type}"],
        }
    ]

_CONFIRM_KEYWORDS = ("好的", "可以", "确认", "开始", "生成", "ok", "OK", "没问题", "继续", "是的")

_VISUAL_KEYWORDS = (
    "配图", "插图", "图片", "示意图", "流程图", "架构图", "结构图",
    "图表", "图解", "配上图", "要图", "带图", "有图",
)

# Query suffixes that orient image search toward technical/教学 imagery rather than
# consumer photos. Style="diagram" in the provider already appends
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


def _ensure_fetch_visuals_when_needed(plan_dict: dict, question: str, capability, state: dict | None = None) -> None:
    """Safety net: LLM-driven plans sometimes omit fetch_visuals even when the
    user explicitly asked for images. Inject it at the appropriate position:
      - If plan has confirm_outline: place fetch_visuals IMMEDIATELY before
        generate_resource (so it runs in the same post-confirm turn).
      - Otherwise: place before generate_resource.

    Visuals intent comes from either the current question or, in the post-
    confirm turn, from active_draft_outline.needs_visuals persisted earlier.
    """
    allow_image_search = bool(getattr(capability, "allow_image_search", False))
    if not allow_image_search:
        return

    # Safety net only fires in the POST-confirm scenario (active_draft_outline
    # exists). In the initial turn we let the LLM-driven plan proceed unmodified;
    # visual intent is carried via active_draft_outline.needs_visuals to the next
    # turn, where this safety net injects fetch_visuals if the next plan misses it.
    outline = (state or {}).get("active_draft_outline") or {}
    if not outline:
        return  # initial turn — do NOT inject

    visuals_from_question = _question_requests_visuals(question)
    visuals_from_outline = bool(outline.get("needs_visuals"))
    if not (visuals_from_question or visuals_from_outline):
        return

    steps = plan_dict.get("steps") or []
    subject = plan_dict.get("subject", "")
    resource_type = plan_dict.get("resource_type", "")

    # Locate the existing fetch_visuals (if any) and generate_resource positions.
    existing_fv_idx = next(
        (i for i, s in enumerate(steps) if s.get("internal_action") == "fetch_visuals"),
        None,
    )
    generate_idx = next(
        (i for i, s in enumerate(steps) if s.get("internal_action") == "generate_resource"),
        len(steps),
    )

    if existing_fv_idx is None:
        # CASE A: missing entirely → inject right before generate_resource
        new_step = {
            "index": generate_idx + 1,
            "user_title": f"为{subject}搜集配图",
            "internal_action": "fetch_visuals",
            "expected_tools": ["image_search"],
            "visual_need": _build_visual_need(subject, resource_type),
        }
        steps.insert(generate_idx, new_step)
        print(
            f"[规划器] 安全网补全：LLM 漏掉 fetch_visuals，已插入到 step {generate_idx + 1}",
            flush=True,
        )
    elif existing_fv_idx + 1 != generate_idx:
        # CASE B: misplaced → move to right before generate_resource so fetch_visuals
        # + generate_resource run within the same turn (avoiding state.accumulated_images
        # being reset across turn boundary).
        misplaced = steps.pop(existing_fv_idx)
        # After pop, generate_resource index may have shifted
        generate_idx = next(
            (i for i, s in enumerate(steps) if s.get("internal_action") == "generate_resource"),
            len(steps),
        )
        steps.insert(generate_idx, misplaced)
        print(
            f"[规划器] 安全网重排：fetch_visuals 从 step {existing_fv_idx + 1} 移到 step {generate_idx + 1}（紧邻 generate_resource）",
            flush=True,
        )
    else:
        return  # already in the right place

    # Reflow 1-based step indices
    for i, s in enumerate(steps):
        s["index"] = i + 1

    plan_dict["steps"] = steps


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
    s = re.sub(r"(报告|分析报告|研究报告|综述报告|PPT课件|PPT|课件|教案|教学设计|教学方案|练习题|测验|题目|习题|教学博客|博客|博文|闪卡|复习卡|记忆卡|思维导图|导图|知识图谱|课堂小游戏|小游戏|教学游戏|AI课堂|AI 课堂|智能课堂|互动课堂)\s*$", "", s, flags=re.IGNORECASE)

    s = s.strip(" .。、,，:：;；")
    return s[:40] if s else question[:40].strip()


def _fallback_plan(question: str, state: dict, capability=None) -> dict:
    resource_type = _explicit_resource_type(question)

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
        # Phase 6-A.2: the confirm message ("生成"/"继续") usually has no visual
        # keywords. Read the intent persisted on active_draft_outline (set by
        # tools_node when draft_outline ran in the previous turn).
        visuals_from_outline = bool(outline.get("needs_visuals"))
        confirm_needs_visuals = allow_image_search and (visuals_from_outline or needs_visuals)
        confirm_steps = []
        if confirm_needs_visuals:
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
    elif resource_type in ("blog", "flashcard", "graph", "game", "classroom"):
        steps = [
            {
                "index": 1,
                "user_title": f"生成{subject}{_RTYPE_CN.get(resource_type, '资源')}",
                "internal_action": "generate_resource",
                "expected_tools": [f"generate_{resource_type}"],
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
            "user_title": "展示大纲并等待用户确认",
            "internal_action": "confirm_outline",
            "expected_tools": [],
        })
        # NOTE: fetch_visuals is intentionally NOT placed before confirm_outline.
        # The user should make a single confirmation on the outline; image search
        # then runs in the SAME turn as generate_resource so accumulated_images
        # survive to injection (state.accumulated_images is per-turn).
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
    "blog":        "教学博客",
    "flashcard":   "闪卡",
    "graph":       "思维导图",
    "game":        "课堂小游戏",
    "classroom":   "AI课堂",
}
