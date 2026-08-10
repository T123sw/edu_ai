"""Trusted lecture context reconstruction and focused classroom Q&A prompts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class StaleClassroomCheckpointError(ValueError):
    pass


class ClassroomQaAnswerError(ValueError):
    pass


@dataclass(frozen=True)
class ClassroomQaContext:
    classroom_title: str
    scene_id: str
    scene_title: str
    scene_speech: tuple[str, ...]
    completed_speech: tuple[str, ...]
    interrupted_speech: str | None
    previous_scene_speech: tuple[str, ...]
    recent_turns: tuple[dict[str, Any], ...]
    rag_answer: str


def build_classroom_qa_context(
    *,
    material: dict[str, Any],
    checkpoint: dict[str, Any],
    recent_turns: list[dict[str, Any]],
    rag_answer: str,
) -> ClassroomQaContext:
    scenes = material.get("scenes")
    scene_index = checkpoint.get("scene_index")
    if (
        not isinstance(scenes, list)
        or not isinstance(scene_index, int)
        or scene_index < 0
        or scene_index >= len(scenes)
    ):
        raise StaleClassroomCheckpointError("scene index is outside the classroom")

    scene = scenes[scene_index]
    if (
        not isinstance(scene, dict)
        or str(scene.get("id") or "") != str(checkpoint.get("scene_id") or "")
    ):
        raise StaleClassroomCheckpointError("scene identity does not match")

    actions = scene.get("actions") or []
    action_index = checkpoint.get("action_index")
    if (
        not isinstance(actions, list)
        or not isinstance(action_index, int)
        or action_index < 0
        or action_index >= len(actions)
    ):
        raise StaleClassroomCheckpointError("action index is outside the scene")
    action = actions[action_index]
    if (
        not isinstance(action, dict)
        or str(action.get("id") or "") != str(checkpoint.get("action_id") or "")
    ):
        raise StaleClassroomCheckpointError("action identity does not match")

    phase = checkpoint.get("phase")
    if phase not in {"executing_action", "between_actions"}:
        raise StaleClassroomCheckpointError("checkpoint phase is invalid")
    if phase == "executing_action" and action.get("type") != "speech":
        raise StaleClassroomCheckpointError(
            "only a speech action can be an interrupted sentence"
        )

    completed_speech = tuple(
        text
        for candidate in actions[:action_index]
        if isinstance(candidate, dict) and candidate.get("type") == "speech"
        if (text := _normalized(candidate.get("text")))
    )
    scene_speech = tuple(
        text
        for candidate in actions
        if isinstance(candidate, dict) and candidate.get("type") == "speech"
        if (text := _normalized(candidate.get("text")))
    )
    interrupted_speech = (
        _normalized(action.get("text")) or None
        if phase == "executing_action"
        else None
    )

    previous_scene_speech: tuple[str, ...] = ()
    if scene_index > 0 and isinstance(scenes[scene_index - 1], dict):
        previous_actions = scenes[scene_index - 1].get("actions") or []
        previous_scene_speech = tuple(
            text
            for candidate in previous_actions
            if isinstance(candidate, dict) and candidate.get("type") == "speech"
            if (text := _normalized(candidate.get("text")))
        )[-3:]

    bounded_history = tuple(
        dict(turn) for turn in list(recent_turns or [])[-6:] if isinstance(turn, dict)
    )
    return ClassroomQaContext(
        classroom_title=_normalized(material.get("title")) or "AI 课堂",
        scene_id=str(scene["id"]),
        scene_title=_normalized(scene.get("title")) or f"第 {scene_index + 1} 页",
        scene_speech=scene_speech,
        completed_speech=completed_speech,
        interrupted_speech=interrupted_speech,
        previous_scene_speech=previous_scene_speech,
        recent_turns=bounded_history,
        rag_answer=_normalized(rag_answer)[:4000],
    )


def build_classroom_qa_messages(
    *,
    question: str,
    context: ClassroomQaContext,
) -> list[dict[str, str]]:
    system = (
        "你是正在授课的 AI 教师。只回答学生当前问题，不创建课件、报告或其他资源。\n"
        "优先结合当前讲授内容，再使用课程知识库参考信息。\n"
        "回答正文通常为 80～300 个中文字符；信息不足时明确边界。\n"
        "另写一句 10～40 个中文字符的自然衔接语，回到当前场景。\n"
        '只输出 JSON：{"answer_text":"...","transition_text":"..."}。'
    )
    history = [
        {
            "question": _normalized(turn.get("question")),
            "answer_text": _normalized(turn.get("answer_text")),
        }
        for turn in context.recent_turns
    ]
    user = "\n".join(
        [
            f"课堂：{context.classroom_title}",
            f"当前场景：{context.scene_title}（{context.scene_id}）",
            f"本场景讲授：{' | '.join(context.scene_speech) or '无'}",
            f"已完成讲授：{' | '.join(context.completed_speech) or '无'}",
            f"被打断句子：{context.interrupted_speech or '无'}",
            f"上一场景末尾：{' | '.join(context.previous_scene_speech) or '无'}",
            "最近问答：" + json.dumps(history, ensure_ascii=False),
            f"课程知识库参考：{context.rag_answer or '无'}",
            f"学生当前问题：{_normalized(question)}",
        ]
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_classroom_qa_answer(
    raw: str,
    *,
    scene_title: str,
) -> tuple[str, str]:
    normalized_raw = str(raw or "").strip()
    if normalized_raw.startswith("```") and normalized_raw.endswith("```"):
        normalized_raw = re.sub(r"^```(?:json)?\s*", "", normalized_raw)
        normalized_raw = re.sub(r"\s*```$", "", normalized_raw).strip()
    if not normalized_raw:
        raise ClassroomQaAnswerError("The classroom answer is empty")

    answer_text: str
    transition_text: str
    try:
        parsed = json.loads(normalized_raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        answer_text = _normalized(parsed.get("answer_text"))
        transition_text = _normalized(parsed.get("transition_text"))
    else:
        answer_text = _normalized(normalized_raw)
        transition_text = ""

    if not answer_text:
        raise ClassroomQaAnswerError("The classroom answer has no answer_text")
    if not transition_text:
        transition_text = f"好，我们回到刚才“{_normalized(scene_title)}”的讲解。"
    return answer_text[:1200], transition_text[:120]


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
