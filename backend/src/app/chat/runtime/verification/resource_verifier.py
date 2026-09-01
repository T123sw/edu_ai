from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.chat.domain.resource_quality import ResourceQualityAssessment


_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "report": {
        "title": ("title", "name", "标题"),
        "content": ("content", "body", "markdown", "sections", "正文", "内容"),
        "structure": ("sections", "outline", "headings", "chapters", "目录", "章节"),
    },
    "lesson_plan": {
        "objectives": ("objectives", "learning_objectives", "goals", "教学目标", "学习目标"),
        "activities": ("activities", "procedure", "steps", "教学过程", "课堂活动"),
        "assessment": ("assessment", "evaluation", "exit_ticket", "评价", "评估"),
    },
    "quiz": {
        "questions": ("questions", "items", "题目", "试题"),
        "answers": ("answers", "answer", "solutions", "答案", "解析"),
    },
    "blog": {
        "title": ("title", "name", "标题"),
        "content": ("content", "body", "markdown", "正文", "内容"),
    },
    "flashcard": {
        "cards": ("cards", "flashcards", "卡片", "闪卡"),
        "front_back": ("front", "back", "question", "answer", "正面", "背面"),
    },
    "graph": {
        "structure": ("root", "nodes", "vertices", "mermaid", "根节点", "节点"),
        "depth_or_relations": ("children", "edges", "links", "relations", "max_depth", "关系", "连线"),
    },
    "game": {
        "title": ("title", "name", "标题"),
        "playable_content": ("game_data", "questions", "items", "categories", "玩法内容"),
        "render_reference": ("html_url", "html_path", "url", "渲染地址"),
    },
    "classroom": {
        "stage": ("stage", "timeline", "课堂舞台"),
        "scenes": ("scenes", "segments", "环节", "场景"),
    },
}


def verify_resource_quality(
    resource_type: str,
    artifact: Mapping[str, Any] | Any,
) -> ResourceQualityAssessment:
    """Validate a persisted resource without asking an LLM to judge facts."""

    kind = str(resource_type or "").strip().lower()
    requirements = _ALIASES.get(kind)
    if not requirements:
        return ResourceQualityAssessment(
            resource_type=kind or "unknown",
            valid=False,
            score=0.0,
            missing_requirements=["supported_resource_type"],
            issues=[f"不支持的资源类型: {kind or 'unknown'}"],
        )

    normalized = _normalize_artifact(artifact)
    searchable = _flatten(normalized)
    satisfied: list[str] = []
    missing: list[str] = []
    for requirement, aliases in requirements.items():
        if _has_requirement(normalized, searchable, aliases):
            satisfied.append(requirement)
        else:
            missing.append(requirement)

    # A report can express structure through markdown headings even when the
    # generator does not expose a dedicated ``sections`` array.
    if kind == "report" and "structure" in missing:
        body = _text_value(normalized, requirements["content"])
        if "##" in body or "\n#" in body or len(body) >= 160:
            missing.remove("structure")
            satisfied.append("structure")

    total = len(requirements)
    score = len(satisfied) / total if total else 0.0
    return ResourceQualityAssessment(
        resource_type=kind,
        valid=not missing,
        score=round(score, 4),
        satisfied_requirements=satisfied,
        missing_requirements=missing,
        issues=[f"缺少质量要素: {item}" for item in missing],
    )


def _normalize_artifact(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, Mapping):
        return {"content": artifact}
    data = dict(artifact)
    material_data = data.get("material_data")
    if isinstance(material_data, Mapping):
        data = {**data, **dict(material_data)}
    generation_state = data.get("generation_state")
    if isinstance(generation_state, Mapping):
        data = {**data, **dict(generation_state)}
    content = data.get("content")
    if isinstance(content, Mapping):
        data = {**data, **dict(content)}
    return data


def _flatten(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str).lower()
    except Exception:
        return str(value).lower()


def _has_requirement(data: dict[str, Any], searchable: str, aliases: tuple[str, ...]) -> bool:
    for key, value in _walk_items(data):
        if str(key).strip().lower() in {alias.lower() for alias in aliases} and _meaningful(value):
            return True
    return any(alias.lower() in searchable for alias in aliases if not alias.isascii())


def _walk_items(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield key, item
            yield from _walk_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_items(item)


def _meaningful(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return len(value.strip()) >= 2
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _text_value(data: dict[str, Any], aliases: tuple[str, ...]) -> str:
    alias_set = {alias.lower() for alias in aliases}
    for key, value in _walk_items(data):
        if str(key).lower() in alias_set and isinstance(value, str):
            return value
    return ""
