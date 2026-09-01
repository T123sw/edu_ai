"""Deterministic extraction of the bounded teacher task vocabulary."""
from __future__ import annotations

import re
from typing import Any

from app.chat.domain.teaching_task_contract import (
    ClarificationDecision,
    ContractAmbiguity,
    ContractFieldEvidence,
    TeachingTaskContract,
)
from app.chat.domain.task_domain import (
    extract_task_ids,
    is_generation_job_id,
    is_learning_task_id,
    partition_task_ids,
    resolve_task_domain,
)


_RESOURCE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lesson_plan", ("教案", "教学设计", "教学方案")),
    ("quiz", ("练习题", "习题", "测验", "题目", "出题")),
    ("blog", ("教学博客", "博客", "博文")),
    ("flashcard", ("闪卡", "复习卡", "记忆卡")),
    ("graph", ("思维导图", "知识图谱", "导图")),
    ("game", ("课堂小游戏", "教学游戏", "小游戏")),
    ("classroom", ("互动 ai 课堂", "互动ai课堂", "ai课堂", "ai 课堂", "智能课堂", "互动课堂")),
    ("report", ("报告", "分析报告", "研究报告")),
)
_BUNDLE_KEYWORDS = ("教学材料", "备课材料", "整套材料", "材料包")
_CANCEL_ACTION_PATTERN = re.compile(
    r"(?:取消|终止|停止)(?:掉|一下)?"
    r"(?:当前|这个|刚才|上一个|最近)?(?:的)?\s*"
    r"(?:学习)?(?:任务|生成|处理|执行|作业|工作流|ai\s*课堂|互动课堂|报告|教案|测验|闪卡|小游戏)"
)
_CANCEL_ONLY_PATTERN = re.compile(r"^(?:请|帮我|现在|立刻|先)?(?:取消|终止|停止)(?:掉|一下)?[。！!\s]*$")
_STATUS_DIRECT_KEYWORDS = ("做到哪", "进度", "完成了吗", "完成没有", "完成情况", "刚完成")
_STATUS_ACTION_PATTERN = re.compile(
    r"(?:(?:任务|生成|处理|执行|作业|工作流|ai\s*课堂).{0,12}状态|"
    r"状态.{0,12}(?:任务|生成|处理|执行|作业|工作流|ai\s*课堂))"
)
_MODIFY_KEYWORDS = ("修改", "改成", "改为", "改得", "改简单", "改难", "调整")
_CONFIRM_EXACT_REPLIES = {
    "开始",
    "好的",
    "可以",
    "确认",
    "没问题",
    "继续",
    "ok",
    "按这个",
    "就按",
    "确认生成",
    "开始生成",
    "继续生成",
    "可以生成",
    "按这个生成",
    "就按这个生成",
}
_CONFIRM_COMMAND_PATTERN = re.compile(
    r"^(?:"
    r"(?:确认)?(?:按这个|就按这个)(?:大纲)?生成"
    r"|确认生成(?:修订后的|修改后的|当前|这份|这个)?"
    r"(?:报告|教案|大纲)?"
    r")$"
)
_WEB_KEYWORDS = ("查找网络", "查网络", "联网", "网上", "最新资料", "网络资料")
_IMAGE_KEYWORDS = ("配图", "插图", "示意图", "流程图", "架构图", "图片")
_GENERATION_KEYWORDS = (
    "生成", "制作", "创建", "做一个", "做一份", "写一份", "写个",
    "准备一个", "准备一份", "整理成", "总结为", "转成", "改写成", "出题",
)
_HOW_TO_PREFIXES = ("如何", "怎么", "怎样", "为什么", "什么是")
_KNOWLEDGE_QUESTION_MARKERS = ("哪些", "什么", "如何", "为什么", "怎么", "怎样")


def extract_task_contract(
    request: Any,
    capability: Any,
    state: dict | None = None,
    *,
    snapshot: Any = None,
) -> TeachingTaskContract:
    state = state or {}
    question = str(getattr(request, "question", "") or "").strip()
    lowered = question.lower()
    agent_memory = dict(state.get("agent_memory") or {})
    working_memory = dict(agent_memory.get("working_memory") or {})
    active_outline = dict(
        state.get("active_draft_outline")
        or working_memory.get("active_outline")
        or {}
    )
    pending_tasks = [
        dict(item)
        for item in (
            state.get("pending_tasks")
            or agent_memory.get("task_ledger")
            or []
        )
        if isinstance(item, dict)
    ]
    resource_types = _resource_types(lowered)

    intent = _intent(lowered, resource_types, active_outline)
    if intent == "prepare_bundle" and not resource_types:
        resource_types = ["lesson_plan", "quiz", "graph"]
    if intent == "confirm" and not resource_types:
        valid_resources = {item[0] for item in _RESOURCE_KEYWORDS}
        outlined_resources = [
            str(item)
            for item in list(active_outline.get("resource_types") or [])
            if str(item) in valid_resources
        ]
        if outlined_resources:
            resource_types = list(dict.fromkeys(outlined_resources))
        else:
            outlined = str(active_outline.get("resource_type") or "report")
            if outlined in valid_resources:
                resource_types = [outlined]

    source_mode, selected_document_ids = _source_authority(capability)
    allow_web = bool(getattr(capability, "allow_web", False))
    allow_images = bool(getattr(capability, "allow_image_search", False))
    requires_images = allow_images and (
        any(keyword in lowered for keyword in _IMAGE_KEYWORDS)
        or (intent == "confirm" and bool(active_outline.get("needs_visuals")))
    )
    web_required = allow_web and (any(keyword in lowered for keyword in _WEB_KEYWORDS) or allow_web)
    # An enabled Web capability is a UI execution directive in this product.
    web_policy = "required" if web_required else ("allowed" if allow_web else "disabled")
    image_policy = "required" if requires_images else ("allowed" if allow_images else "disabled")
    topic = _topic(question, resource_types, active_outline)
    question_count = _question_count(lowered)
    audience = _audience(question)
    lesson_duration = _lesson_duration(question)
    constraints: dict = {}
    if question_count is not None:
        constraints["question_count"] = question_count

    confirmation_required = intent in {"prepare_bundle"} or any(
        resource in {"report", "lesson_plan", "classroom"} for resource in resource_types
    )
    if intent == "confirm":
        confirmation_policy = "none"
    elif confirmation_required:
        confirmation_policy = "required"
    else:
        confirmation_policy = "none"

    historical_generation_job_ids = [
        str(item.get("task_id") or "").strip()
        for item in pending_tasks
        if is_generation_job_id(item.get("task_id") or "")
    ]
    historical_learning_task_ids = [
        str(item.get("task_id") or "").strip()
        for item in pending_tasks
        if is_learning_task_id(item.get("task_id") or "")
    ]
    current_learning_task_ids, current_generation_job_ids = partition_task_ids(
        extract_task_ids(question)
    )
    page_task_ids = _page_task_ids(snapshot)
    page_learning_task_ids, page_generation_job_ids = partition_task_ids(page_task_ids)
    task_domain = resolve_task_domain(
        question,
        historical_learning_task_ids + historical_generation_job_ids,
        page_task_ids=page_task_ids,
    )
    domain_pending_tasks = {
        "course_learning": [
            item for item in pending_tasks
            if is_learning_task_id(item.get("task_id") or "")
        ],
        "generation_job": [
            item for item in pending_tasks
            if is_generation_job_id(item.get("task_id") or "")
        ],
    }.get(task_domain, [])
    ambiguities = _ambiguities(
        question=question,
        intent=intent,
        resource_types=resource_types,
        pending_tasks=domain_pending_tasks,
    )
    clarification = _clarification(ambiguities)
    field_evidence = _field_evidence(
        question=question,
        intent=intent,
        topic=topic,
        resource_types=resource_types,
        source_mode=source_mode,
        selected_document_ids=selected_document_ids,
        audience=audience,
        lesson_duration=lesson_duration,
        active_outline=active_outline,
    )

    return TeachingTaskContract(
        actor_role=(
            "student"
            if str(getattr(request, "actor_role", "teacher") or "").strip().lower() == "student"
            else "teacher"
        ),
        intent=intent,
        task_domain=task_domain,
        topic=topic,
        resource_types=resource_types,
        audience=audience,
        lesson_duration=lesson_duration,
        constraints=constraints,
        source_mode=source_mode,
        selected_document_ids=selected_document_ids,
        web_policy=web_policy,
        image_policy=image_policy,
        confirmation_policy=confirmation_policy,
        conversation_refs={
            "conversation_id": str(getattr(request, "conversation_id", "") or ""),
            "course_id": str(getattr(request, "course_id", "") or ""),
            "active_outline": bool(active_outline),
            "current_learning_task_ids": current_learning_task_ids,
            "current_generation_job_ids": current_generation_job_ids,
            "page_learning_task_ids": page_learning_task_ids,
            "page_generation_job_ids": page_generation_job_ids,
            "learning_task_ids": historical_learning_task_ids,
            "generation_job_ids": historical_generation_job_ids,
        },
        field_evidence=field_evidence,
        ambiguities=ambiguities,
        clarification=clarification,
    )


def _page_task_ids(snapshot: Any) -> list[str]:
    """Read task IDs only from structured snapshot fields owned by the page."""
    if snapshot is None:
        return []

    values: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                add(item)

    learning_context = dict(getattr(snapshot, "learning_context", {}) or {})
    for key in ("pending_tasks", "completed_tasks", "task_summaries"):
        for item in list(learning_context.get(key) or []):
            if isinstance(item, dict):
                add(item.get("task_id"))

    active_context = dict(getattr(snapshot, "active_context", {}) or {})
    for key in (
        "task_id",
        "task_ids",
        "active_task_id",
        "learning_task_id",
        "learning_task_ids",
        "generation_job_id",
        "generation_job_ids",
    ):
        add(active_context.get(key))
    add(getattr(snapshot, "active_task", None))
    add(getattr(snapshot, "referenced_artifact_ids", []))

    workflow_state = getattr(snapshot, "workflow_state", None)
    if isinstance(workflow_state, dict):
        add(workflow_state.get("workflow_id"))
    else:
        add(getattr(workflow_state, "workflow_id", None))
    return [
        value for value in values
        if is_learning_task_id(value) or is_generation_job_id(value)
    ]


def _intent(question: str, resource_types: list[str], active_outline: dict) -> str:
    if _is_cancel_request(question):
        return "cancel"
    if _is_status_request(question):
        return "status"
    if _is_modification_request(question, resource_types, active_outline):
        return "modify"
    if active_outline and _is_outline_confirmation(question):
        return "confirm"
    if any(question.startswith(prefix) for prefix in _HOW_TO_PREFIXES):
        return "qa"
    if any(keyword in question for keyword in _BUNDLE_KEYWORDS):
        return "prepare_bundle"
    if resource_types and _requests_generation(question):
        return "generate_single"
    if resource_types and _looks_like_direct_resource_request(question):
        return "generate_single"
    if _requests_generation(question):
        return "generate_single"
    return "qa"


def _is_outline_confirmation(question: str) -> bool:
    normalized = re.sub(
        r"[\s，,。.!！?？]+",
        "",
        str(question or "").lower(),
    )
    return (
        normalized in _CONFIRM_EXACT_REPLIES
        or bool(_CONFIRM_COMMAND_PATTERN.fullmatch(normalized))
    )


def _is_cancel_request(question: str) -> bool:
    """Recognise an explicit task-control command, not a subject concept.

    Terms such as ``停止条件`` and ``终止状态`` are common in algorithm
    questions.  Treating the bare character sequence as a cancel command made
    ordinary student questions abort the current workflow.
    """

    normalized = str(question or "").strip().lower()
    return bool(
        _CANCEL_ACTION_PATTERN.search(normalized)
        or _CANCEL_ONLY_PATTERN.fullmatch(normalized)
    )


def _is_status_request(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    return bool(
        any(keyword in normalized for keyword in _STATUS_DIRECT_KEYWORDS)
        or _STATUS_ACTION_PATTERN.search(normalized)
    )


def _is_modification_request(
    question: str,
    resource_types: list[str],
    active_outline: dict,
) -> bool:
    if not any(keyword in question for keyword in _MODIFY_KEYWORDS):
        return False
    has_action_target = bool(active_outline) or bool(re.search(
        r"(?:把|将|刚才|这份|这个|当前).{0,24}(?:修改|改成|改为|改得|改简单|改难|调整)",
        question,
    ))
    if has_action_target:
        return True
    if any(marker in question for marker in _KNOWLEDGE_QUESTION_MARKERS):
        return False
    return bool(resource_types and re.search(r"(?:修改|改简单|改难|调整为)", question))


def _requests_generation(question: str) -> bool:
    if re.search(r"(?:不要|无需|不必|先不|暂不)(?:调用.{0,8})?(?:生成|制作|创建)", question):
        return False
    normalized = question.replace("生成式", "")
    return any(keyword in normalized for keyword in _GENERATION_KEYWORDS)


def _looks_like_direct_resource_request(question: str) -> bool:
    """Recognise terse creation commands without treating a resource noun as intent.

    A mention such as ``教案包含哪些部分`` is a knowledge question.  Commands
    such as ``给我一份教案`` still need to enter generation even when the user
    omits the verb ``生成``.
    """
    normalized = str(question or "").strip().lower()
    if any(marker in normalized for marker in _KNOWLEDGE_QUESTION_MARKERS):
        return False
    return bool(re.search(
        r"(?:^|[，,。；;\s])(?:给我|来|帮我准备|请准备|准备|编写|出)"
        r".{0,24}(?:教案|教学设计|教学方案|练习题|习题|测验|题目|"
        r"教学博客|博客|博文|闪卡|复习卡|记忆卡|思维导图|知识图谱|导图|"
        r"课堂小游戏|教学游戏|小游戏|ai\s*课堂|智能课堂|互动课堂|报告)",
        normalized,
    ))


def _resource_types(question: str) -> list[str]:
    return [resource for resource, keywords in _RESOURCE_KEYWORDS if any(keyword in question for keyword in keywords)]


def _source_authority(capability: Any) -> tuple[str, list[str]]:
    selected = list(getattr(capability, "selected_doc_ids", []) or [])
    source_mode = str(getattr(capability, "source_mode", "") or "")
    if selected or source_mode == "selected_documents":
        return "selected_documents", selected
    if source_mode == "course_auto" or bool(getattr(capability, "allow_rag", False)):
        return "course_auto", []
    return "none", []


def _topic(question: str, resource_types: list[str], active_outline: dict) -> str:
    if active_outline and (
        _is_outline_confirmation(question)
        or any(token in question.lower() for token in _MODIFY_KEYWORDS)
    ):
        return str(active_outline.get("subject") or "").strip()
    topic = question
    for _, keywords in _RESOURCE_KEYWORDS:
        for keyword in keywords:
            topic = re.sub(re.escape(keyword), "", topic, flags=re.IGNORECASE)
    # Audience and duration are first-class contract fields; keeping them in
    # the topic polluted plan titles and generated material names (for example
    # ``为高一学生一份链表教学``).  Strip only explicit, already-recognised
    # teacher constraints so the actual subject remains intact.
    topic = re.sub(
        r"(?:为|给)?(?:(?:基础薄弱|零基础)(?:的)?)?"
        r"(?:小学|初一|初二|初三|初中|高一|高二|高三|高中|中职|大学)学生",
        "",
        topic,
    )
    topic = re.sub(r"\d{1,3}\s*分钟", "", topic)
    topic = re.sub(r"(?:带|包含|配有)?(?:流程图|架构图|示意图|配图|插图|图片)的?", "", topic)
    for keyword in (*_BUNDLE_KEYWORDS, "生成", "制作", "写一份", "帮我", "准备", "查找网络", "查网络"):
        topic = topic.replace(keyword, "")
    # Do not globally remove conjunction characters: ``并`` is part of valid
    # subjects such as ``归并排序``.  Only trim them when they are leading
    # command glue left behind by removed action phrases.
    topic = re.sub(r"^(?:并且?|和|以及)", "", topic)
    topic = re.sub(r"^(?:请|请为|为|给|一份|一个|讲解)+", "", topic)
    topic = re.sub(r"的$", "", topic)
    topic = re.sub(r"(?:\d+\s*道|\d+\s*个)", "", topic)
    topic = re.sub(r"[，,。；;：:\s]+", " ", topic).strip(" ，,。；;：:")
    return topic or str(active_outline.get("subject") or "教学主题")


def _question_count(question: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*道", question)
    if match:
        return int(match.group(1))
    chinese = re.search(r"([一二三四五六七八九十])\s*道", question)
    if not chinese:
        return None
    value = chinese.group(1)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    return digits[value]


def _audience(question: str) -> str | None:
    match = re.search(
        r"((?:(?:基础薄弱|零基础)(?:的)?)?"
        r"(?:小学|初一|初二|初三|初中|高一|高二|高三|高中|中职|大学)学生)",
        question,
    )
    if match:
        return match.group(1)
    generic = re.search(r"((?:基础薄弱|零基础)(?:的)?学生)", question)
    return generic.group(1) if generic else None


def _lesson_duration(question: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*分钟", question)
    if not match:
        return None
    value = int(match.group(1))
    return value if 5 <= value <= 300 else None


def _ambiguities(
    *,
    question: str,
    intent: str,
    resource_types: list[str],
    pending_tasks: list[dict],
) -> list[ContractAmbiguity]:
    if intent == "generate_single" and not resource_types:
        return [ContractAmbiguity(
            field="resource_types",
            impact="high",
            reason="用户要求生成资源，但没有说明资源类型",
            candidates=["lesson_plan", "quiz", "report", "blog"],
        )]
    if intent in {"status", "cancel"} and len(pending_tasks) > 1:
        named_types = {
            str(item.get("workflow_type") or "").lower()
            for item in pending_tasks
            if str(item.get("workflow_type") or "").strip()
        }
        question_lower = question.lower()
        names_target = any(
            keyword in question_lower
            for resource, keywords in _RESOURCE_KEYWORDS
            if resource in named_types
            for keyword in keywords
        )
        if not names_target and not re.search(r"\b(?:job|task)[-_]?[a-z0-9]+\b", question_lower):
            return [ContractAmbiguity(
                field="task_reference",
                impact="high",
                reason="当前对话存在多个候选任务",
                candidates=[
                    str(item.get("task_id") or "") for item in pending_tasks
                    if str(item.get("task_id") or "").strip()
                ],
            )]
    return []


def _clarification(ambiguities: list[ContractAmbiguity]) -> ClarificationDecision:
    high = next((item for item in ambiguities if item.impact == "high"), None)
    if high is None:
        return ClarificationDecision(required=False, budget=1)
    questions = {
        "resource_types": "你希望生成哪种教学资源（教案、练习题、报告或其他）？",
        "task_reference": "当前有多个任务，你指的是哪一个？",
    }
    return ClarificationDecision(
        required=True,
        field=high.field,
        question=questions.get(high.field, "请补充一个会影响执行结果的关键信息。"),
        budget=1,
        reason=high.reason,
    )


def _field_evidence(
    *,
    question: str,
    intent: str,
    topic: str,
    resource_types: list[str],
    source_mode: str,
    selected_document_ids: list[str],
    audience: str | None,
    lesson_duration: int | None,
    active_outline: dict,
) -> dict[str, ContractFieldEvidence]:
    state_topic = bool(active_outline) and intent in {"confirm", "modify"}
    evidence: dict[str, ContractFieldEvidence] = {
        "intent": ContractFieldEvidence(
            origin="inferred", confidence=0.98, reason="确定性意图规则", value=intent
        ),
        "topic": ContractFieldEvidence(
            origin="state" if state_topic else "user",
            confidence=1.0 if state_topic else 0.92,
            reason="活动大纲主题" if state_topic else "用户消息主题抽取",
            value=topic,
        ),
        "resource_types": ContractFieldEvidence(
            origin=(
                "state" if intent == "confirm" and active_outline
                else "default" if intent == "prepare_bundle" and resource_types
                else "user"
            ),
            confidence=1.0 if resource_types else 0.0,
            reason="资源关键词、材料包默认值或活动大纲",
            value=resource_types,
        ),
        "source_mode": ContractFieldEvidence(
            origin="ui", confidence=1.0, reason="UI capability 为来源事实权威", value=source_mode
        ),
        "selected_document_ids": ContractFieldEvidence(
            origin="ui", confidence=1.0, reason="UI 已选文档不可由模型覆盖", value=selected_document_ids
        ),
    }
    if audience:
        evidence["audience"] = ContractFieldEvidence(
            origin="user", confidence=0.96, reason="用户显式学情/年级", value=audience
        )
    if lesson_duration is not None:
        evidence["lesson_duration"] = ContractFieldEvidence(
            origin="user", confidence=1.0, reason="用户显式分钟数", value=lesson_duration
        )
    return evidence
