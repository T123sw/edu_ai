"""Normalize existing quiz-bearing course materials into assessment items."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .models import AssessmentItemRecord


@dataclass(frozen=True)
class ExtractionResult:
    items: list[AssessmentItemRecord]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _question_type(raw_type: Any, answer: Any) -> str:
    value = _text(raw_type).lower()
    if value in {"multiple", "multiple_choice", "multi_choice"} or isinstance(answer, list):
        return "multiple_choice"
    if value in {"blank", "fill", "fill_blank", "structured_blank"}:
        return "structured_blank"
    if value in {"short", "short_answer", "essay"}:
        return "short_answer"
    if value in {"judge", "true_false", "boolean"}:
        return "judge"
    if value in {"code_output", "code_trace", "debug_fix", "code_implementation"}:
        return value
    return "single_choice"


def _options(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    values: list[dict[str, str]] = []
    for index, option in enumerate(raw, start=1):
        if isinstance(option, dict):
            label = _text(option.get("text") or option.get("content") or option.get("label"))
        else:
            label = _text(option)
        if label:
            values.append({"id": f"opt-{index}", "text": label})
    return values


def _option_id(answer: Any, options: list[dict[str, str]]) -> str:
    value = _text(answer)
    if not value:
        return ""
    normalized = value.upper().strip(".、 ")
    if len(normalized) == 1 and "A" <= normalized <= "Z":
        index = ord(normalized) - ord("A")
        return options[index]["id"] if index < len(options) else ""
    for option in options:
        if option["text"].casefold() == value.casefold():
            return option["id"]
    if any(option["id"] == value for option in options):
        return value
    return ""


def _multiple_option_ids(answer: Any, options: list[dict[str, str]]) -> list[str]:
    raw_values = answer if isinstance(answer, list) else re.split(r"[,，、|/\s]+", _text(answer))
    resolved = [_option_id(value, options) for value in raw_values]
    return sorted({value for value in resolved if value})


def _judge_value(answer: Any) -> bool | None:
    if isinstance(answer, bool):
        return answer
    value = _text(answer).casefold()
    if value in {"true", "正确", "对", "是", "1"}:
        return True
    if value in {"false", "错误", "错", "否", "0"}:
        return False
    return None


def normalize_question(
    raw: dict[str, Any],
    *,
    assessment_version_id: str,
    position: int,
    knowledge_point_ids: list[str],
    source_ref: dict[str, Any],
    created_origin: str,
) -> AssessmentItemRecord:
    answer = raw.get("answer", raw.get("correct_answer"))
    item_type = _question_type(raw.get("type"), answer)
    options = _options(raw.get("options") or raw.get("choices"))
    stem = _text(
        raw.get("stem")
        or raw.get("question")
        or raw.get("content")
        or raw.get("title")
    )
    prompt: dict[str, Any] = {"stem": stem}
    if options:
        prompt["options"] = options
    scoring_key: dict[str, Any] = {}
    if item_type == "single_choice":
        correct_option_id = _option_id(answer, options)
        if correct_option_id:
            scoring_key = {"correct_option_id": correct_option_id}
    elif item_type == "multiple_choice":
        correct_option_ids = _multiple_option_ids(answer, options)
        if correct_option_ids:
            scoring_key = {"correct_option_ids": correct_option_ids}
    elif item_type == "judge":
        correct_value = _judge_value(answer)
        if correct_value is not None:
            scoring_key = {"correct_value": correct_value}
    elif item_type in {"structured_blank", "code_output", "code_trace", "debug_fix"}:
        answers = answer if isinstance(answer, list) else [answer]
        accepted = [_text(value) for value in answers if _text(value)]
        if accepted:
            scoring_key = {"accepted_answers": accepted}

    explanation = _text(raw.get("explanation") or raw.get("analysis"))
    reference_answer = _text(answer)
    rubric = {}
    grading_provider = "deterministic"
    if item_type in {"short_answer", "artifact", "code_implementation"}:
        grading_provider = "rubric_ai_teacher"
        if reference_answer or explanation:
            rubric = {
                "reference_answer": reference_answer,
                "criteria": [explanation or reference_answer],
            }
    elif explanation:
        rubric = {"explanation": explanation}

    return AssessmentItemRecord.new(
        assessment_version_id=assessment_version_id,
        position=position,
        item_type=item_type,
        prompt=prompt,
        scoring_key=scoring_key,
        rubric=rubric,
        max_score=float(raw.get("points") or raw.get("max_score") or 10),
        grading_provider=grading_provider,
        knowledge_point_ids=knowledge_point_ids,
        source_refs=[source_ref],
        created_origin=created_origin,
        source_exposure_state=(
            "possibly_public"
            if str(source_ref.get("material_type")) == "quiz"
            else "private"
        ),
    )


def _material_questions(material: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    material_type = _text(material.get("material_type"))
    material_id = _text(material.get("material_id"))
    base_ref = {"material_type": material_type, "material_id": material_id}
    if material_type == "quiz":
        content = material.get("content") if isinstance(material.get("content"), dict) else {}
        questions = material.get("questions") or content.get("questions") or []
        for index, question in enumerate(questions, start=1):
            if isinstance(question, dict):
                yield question, {
                    **base_ref,
                    "source_item_id": _text(question.get("id")) or str(index),
                }
    if material_type == "classroom":
        content = material.get("content") if isinstance(material.get("content"), dict) else {}
        scenes = material.get("scenes") or content.get("scenes") or []
        for scene_index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict) or _text(scene.get("type")) != "quiz":
                continue
            scene_content = scene.get("content") if isinstance(scene.get("content"), dict) else {}
            for question_index, question in enumerate(scene_content.get("questions") or [], start=1):
                if isinstance(question, dict):
                    yield question, {
                        **base_ref,
                        "scene_id": _text(scene.get("id")) or str(scene_index),
                        "source_item_id": _text(question.get("id")) or str(question_index),
                    }


def extract_assessment_items(
    materials: list[dict[str, Any]],
    *,
    assessment_version_id: str,
    knowledge_point_ids: list[str],
) -> ExtractionResult:
    items: list[AssessmentItemRecord] = []
    for material in materials:
        for raw, source_ref in _material_questions(material):
            items.append(
                normalize_question(
                    raw,
                    assessment_version_id=assessment_version_id,
                    position=len(items) + 1,
                    knowledge_point_ids=list(knowledge_point_ids),
                    source_ref=source_ref,
                    created_origin="imported",
                )
            )
    return ExtractionResult(items=items)
