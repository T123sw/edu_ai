"""Extract and select bounded evidence from complete static learning resources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.services.classroom_qa_prompt import ClassroomQaAnswerError


ResourceKind = Literal["study_guide", "practice"]

_ANSWER_KEYS = {
    "answer",
    "answers",
    "correctanswer",
    "solution",
    "explanation",
    "解析",
    "标准答案",
}


@dataclass(frozen=True)
class ResourceQaSection:
    label: str
    text: str
    scene_id: str | None = None
    page_number: int | None = None
    question_id: str | None = None


@dataclass(frozen=True)
class ResourceQaContext:
    resource_kind: ResourceKind
    resource_title: str
    selected_sections: tuple[ResourceQaSection, ...]
    include_answers: bool


def build_resource_qa_context(
    *,
    resource_kind: ResourceKind,
    material: dict[str, Any],
    question: str,
    anchor: dict[str, Any] | None,
    include_answers: bool,
) -> ResourceQaContext:
    if resource_kind == "practice":
        sections = _extract_practice_sections(material, include_answers=include_answers)
    else:
        sections = _extract_document_sections(material)
    selected = _select_sections(question, sections, anchor=anchor, limit=16)
    return ResourceQaContext(
        resource_kind=resource_kind,
        resource_title=_normalized(material.get("title")) or "学习资料",
        selected_sections=selected,
        include_answers=include_answers,
    )


def build_resource_qa_messages(
    *,
    question: str,
    context: ResourceQaContext,
    recent_turns: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> list[dict[str, str]]:
    answer_policy = (
        "当前是学生习题模式：禁止猜测或泄露标准答案、正确选项和解析；可以解释相关知识与解题思路。"
        if context.resource_kind == "practice" and not context.include_answers
        else "可以依据提供内容回答，但不得补造资料中不存在的事实。"
    )
    system = (
        "你是课程学习区的 AI 助教。只基于服务端提供的完整资源相关段落回答当前问题。\n"
        f"{answer_policy}\n"
        "回答正文通常为 80～500 个中文字符；证据不足时明确说明。\n"
        "transition_text 用一句简短的话引导用户继续查看当前资料。\n"
        '只输出 JSON：{"answer_text":"...","transition_text":"..."}。'
    )
    evidence = [
        {"label": section.label, "text": section.text}
        for section in context.selected_sections
    ]
    history = [
        {
            "question": _normalized(turn.get("question")),
            "answer_text": _normalized(turn.get("answer_text")),
        }
        for turn in list(recent_turns)[-6:]
        if isinstance(turn, dict)
    ]
    user = "\n".join(
        [
            f"资料：{context.resource_title}",
            f"资料类型：{context.resource_kind}",
            "完整资源相关段落：" + json.dumps(evidence, ensure_ascii=False),
            "最近问答：" + json.dumps(history, ensure_ascii=False),
            f"用户当前问题：{_normalized(question)}",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_resource_qa_answer(raw: str, *, resource_title: str) -> tuple[str, str]:
    normalized_raw = str(raw or "").strip()
    if normalized_raw.startswith("```") and normalized_raw.endswith("```"):
        normalized_raw = re.sub(r"^```(?:json)?\s*", "", normalized_raw)
        normalized_raw = re.sub(r"\s*```$", "", normalized_raw).strip()
    if not normalized_raw:
        raise ClassroomQaAnswerError("The resource answer is empty")
    try:
        parsed = json.loads(normalized_raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        answer = _normalized(parsed.get("answer_text"))
        transition = _normalized(parsed.get("transition_text"))
    else:
        answer = _normalized(normalized_raw)
        transition = ""
    if not answer:
        raise ClassroomQaAnswerError("The resource answer has no answer_text")
    if not transition:
        transition = f"可以继续对照“{_normalized(resource_title)}”查看相关内容。"
    return answer[:1200], transition[:120]


def _extract_document_sections(material: dict[str, Any]) -> tuple[ResourceQaSection, ...]:
    sections: list[ResourceQaSection] = []

    def walk(value: Any, path: str, page_number: int | None = None) -> None:
        if isinstance(value, str):
            text = _normalized(value)
            if text:
                sections.extend(_bounded_sections(path or "root", text, page_number=page_number))
            return
        if isinstance(value, list):
            is_page_list = path.endswith("sections") or path.endswith("blocks") or path.endswith("pages")
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]", index + 1 if is_page_list else page_number)
            return
        if isinstance(value, dict):
            explicit_page = value.get("page_number")
            next_page = explicit_page if isinstance(explicit_page, int) and explicit_page > 0 else page_number
            for key, item in value.items():
                if key in {"created_at", "updated_at", "content_hash"}:
                    continue
                walk(item, f"{path}.{key}" if path else str(key), next_page)

    walk(material, "")
    return tuple(sections)


def _extract_practice_sections(
    material: dict[str, Any],
    *,
    include_answers: bool,
) -> tuple[ResourceQaSection, ...]:
    questions = _find_questions(material)
    result: list[ResourceQaSection] = []
    for index, raw_question in enumerate(questions, start=1):
        safe_question = raw_question if include_answers else _remove_answer_fields(raw_question)
        question_id = _normalized(raw_question.get("id")) or _normalized(raw_question.get("question_id")) or f"question-{index}"
        lines = [f"题目 {index}"]
        lines.extend(_labeled_string_leaves(safe_question))
        text = "\n".join(dict.fromkeys(line for line in lines if line))
        result.extend(
            _bounded_sections(
                f"questions[{index - 1}] · 题目 {index}",
                text,
                page_number=index,
                question_id=question_id,
            )
        )
    return tuple(result)


def _find_questions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        questions = value.get("questions")
        if isinstance(questions, list):
            return [item for item in questions if isinstance(item, dict)]
        for item in value.values():
            found = _find_questions(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_questions(item)
            if found:
                return found
    return []


def _remove_answer_fields(value: Any) -> Any:
    if isinstance(value, list):
        return [_remove_answer_fields(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _remove_answer_fields(item)
            for key, item in value.items()
            if _answer_key(key) not in _ANSWER_KEYS
        }
    return value


def _labeled_string_leaves(value: Any, path: str = "") -> list[str]:
    if isinstance(value, str):
        text = _normalized(value)
        return [f"{path}: {text}" if path else text] if text else []
    if isinstance(value, list):
        return [
            line
            for index, item in enumerate(value)
            for line in _labeled_string_leaves(item, f"{path}[{index}]")
        ]
    if isinstance(value, dict):
        return [
            line
            for key, item in value.items()
            for line in _labeled_string_leaves(item, f"{path}.{key}" if path else str(key))
        ]
    return []


def _select_sections(
    question: str,
    sections: tuple[ResourceQaSection, ...],
    *,
    anchor: dict[str, Any] | None,
    limit: int,
) -> tuple[ResourceQaSection, ...]:
    if not sections or limit <= 0:
        return ()
    anchored = [section for section in sections if _matches_anchor(section, anchor)]
    anchored_ids = {id(section) for section in anchored}
    terms = _question_terms(question)
    scored: list[tuple[int, int, ResourceQaSection]] = []
    for index, section in enumerate(sections):
        if id(section) in anchored_ids:
            continue
        lowered = section.text.lower()
        score = sum((len(term) ** 2) * lowered.count(term) for term in terms)
        if score:
            scored.append((score, index, section))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = list(anchored[:limit])
    selected.extend(item[2] for item in scored[: max(0, limit - len(selected))])
    if not scored and len(selected) < limit:
        sample_count = min(limit - len(selected), len(sections))
        for index in _even_indices(len(sections), sample_count):
            section = sections[index]
            if id(section) not in {id(item) for item in selected}:
                selected.append(section)
    order = {id(section): index for index, section in enumerate(sections)}
    return tuple(sorted(selected[:limit], key=lambda item: order[id(item)]))


def _matches_anchor(section: ResourceQaSection, anchor: dict[str, Any] | None) -> bool:
    if not anchor:
        return False
    return any(
        anchor.get(key) is not None and anchor.get(key) == getattr(section, key)
        for key in ("scene_id", "page_number", "question_id")
    )


def _bounded_sections(
    label: str,
    text: str,
    *,
    page_number: int | None = None,
    question_id: str | None = None,
) -> list[ResourceQaSection]:
    return [
        ResourceQaSection(
            label=label if start == 0 else f"{label} · 续 {start // 1600 + 1}",
            text=text[start : start + 1600],
            page_number=page_number,
            question_id=question_id,
        )
        for start in range(0, len(text), 1600)
    ]


def _even_indices(length: int, count: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1 or length == 1:
        return [0]
    return sorted({round(index * (length - 1) / (count - 1)) for index in range(count)})


def _question_terms(question: str) -> tuple[str, ...]:
    terms: set[str] = set()
    for token in re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", question.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            terms.update(token[index : index + 2] for index in range(max(0, len(token) - 1)))
            if len(token) <= 12:
                terms.add(token)
        elif len(token) > 1:
            terms.add(token)
    return tuple(terms)


def _answer_key(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"解析", "标准答案"}:
        return text
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
