"""Task-domain classification for learning and generation task control."""
from __future__ import annotations

import re
from typing import Literal


TaskDomain = Literal["none", "course_learning", "generation_job"]

_LEARNING = ("学习任务", "学习进度", "完成率", "学生完成", "待学习", "刚完成")
_GENERATION = ("生成任务", "生成进度", "生成完成", "后台任务", "闪卡生成", "报告生成")
_TASK_ID = re.compile(r"\b(?:lt|job)_[a-zA-Z0-9_-]+\b")


def resolve_task_domain(question: str, explicit_task_ids: list[str] | None = None) -> TaskDomain:
    """Resolve the current request before consulting historical task references.

    IDs written in this turn are explicit user intent.  Historical IDs supplied
    by the caller are only a fallback when the current message has no explicit
    learning or generation signal.
    """
    text = str(question or "").strip().lower()
    current_ids = _TASK_ID.findall(text)
    has_current_learning_id = any(value.startswith("lt_") for value in current_ids)
    has_current_generation_id = any(value.startswith("job_") for value in current_ids)
    if has_current_learning_id and has_current_generation_id:
        return "none"
    if has_current_learning_id:
        return "course_learning"
    if has_current_generation_id:
        return "generation_job"

    learning = any(token in text for token in _LEARNING)
    generation = any(token in text for token in _GENERATION)
    if learning and generation:
        return "none"
    if learning and not generation:
        return "course_learning"
    if generation and not learning:
        return "generation_job"

    historical_ids = list(explicit_task_ids or [])
    has_historical_learning_id = any(value.startswith("lt_") for value in historical_ids)
    has_historical_generation_id = any(value.startswith("job_") for value in historical_ids)
    if has_historical_learning_id and has_historical_generation_id:
        return "none"
    if has_historical_learning_id:
        return "course_learning"
    if has_historical_generation_id:
        return "generation_job"
    return "none"
