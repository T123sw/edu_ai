"""Task-domain classification for learning and generation task control."""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal


TaskDomain = Literal["none", "course_learning", "generation_job"]

_LEARNING = ("学习任务", "学习进度", "完成率", "学生完成", "待学习", "刚完成")
_GENERATION = ("生成任务", "生成进度", "生成完成", "后台任务", "闪卡生成", "报告生成")
_TASK_ID = re.compile(r"\b(?:lt_[a-zA-Z0-9_-]+|job(?:_|-)[a-zA-Z0-9_-]+)\b")
_NEGATED_MENTION = re.compile(r"(?:不|不要|无需|别|禁止|不得|而非|不是)[^，。！？；]{0,8}$")


def is_learning_task_id(value: str) -> bool:
    return str(value or "").strip().startswith("lt_")


def is_generation_job_id(value: str) -> bool:
    return str(value or "").strip().startswith(("job_", "job-"))


def extract_task_ids(question: str) -> list[str]:
    return _TASK_ID.findall(str(question or "").strip().lower())


def partition_task_ids(task_ids: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return learning and generation IDs while preserving their source order."""
    learning: list[str] = []
    generation: list[str] = []
    for raw in task_ids:
        value = str(raw or "").strip()
        if is_learning_task_id(value):
            learning.append(value)
        elif is_generation_job_id(value):
            generation.append(value)
    return learning, generation


def _domain_from_ids(task_ids: Iterable[str]) -> TaskDomain:
    learning, generation = partition_task_ids(task_ids)
    if learning and generation:
        return "none"
    if learning:
        return "course_learning"
    if generation:
        return "generation_job"
    return "none"


def _has_affirmed_token(text: str, tokens: Iterable[str]) -> bool:
    """Ignore a domain name when it only appears in a local negation clause."""
    for token in tokens:
        for match in re.finditer(re.escape(token), text):
            prefix = text[max(0, match.start() - 12):match.start()]
            if not _NEGATED_MENTION.search(prefix):
                return True
    return False


def resolve_task_domain(
    question: str,
    explicit_task_ids: list[str] | None = None,
    *,
    page_task_ids: list[str] | None = None,
) -> TaskDomain:
    """Resolve current request, page context, then historical task references.

    ``explicit_task_ids`` remains the backwards-compatible historical-reference
    parameter.  IDs written in ``question`` are the current request and take
    precedence; structured page IDs are consulted next; historical IDs are a
    fallback only when neither source identifies a domain.
    """
    text = str(question or "").strip().lower()
    current_ids = extract_task_ids(text)
    if current_ids:
        return _domain_from_ids(current_ids)

    learning = _has_affirmed_token(text, _LEARNING)
    generation = _has_affirmed_token(text, _GENERATION)
    if learning or generation:
        if learning and generation:
            return "none"
        return "course_learning" if learning else "generation_job"

    structured_page_ids = list(page_task_ids or [])
    if structured_page_ids:
        return _domain_from_ids(structured_page_ids)

    historical_ids = list(explicit_task_ids or [])
    if historical_ids:
        return _domain_from_ids(historical_ids)
    return "none"
