"""Task-domain classification for learning and generation task control."""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal


TaskDomain = Literal["none", "course_learning", "generation_job"]

_LEARNING = ("学习任务", "学习进度", "完成率", "学生完成", "待学习", "刚完成")
_GENERATION = ("生成任务", "生成进度", "生成完成", "后台任务", "闪卡生成", "报告生成")
_TASK_ID = re.compile(r"\b(?:lt_[a-zA-Z0-9_-]+|job(?:_|-)[a-zA-Z0-9_-]+)\b")


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

    learning = any(token in text for token in _LEARNING)
    generation = any(token in text for token in _GENERATION)
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
