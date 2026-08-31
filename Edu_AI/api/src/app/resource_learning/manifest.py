from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from .models import ManifestQuestion, ManifestScene, ResourceLearningManifestRecord, SceneKind


_SCENE_KIND: dict[str, SceneKind] = {
    "slide": "explanation",
    "quiz": "exercise",
    "interactive": "demo",
}
_FOCUS_ACTIONS = frozenset({"spotlight", "laser", "focus"})
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af]")


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    values = _as_sequence(value)
    if not values:
        text = str(value).strip()
        return (text,) if text else ()
    return tuple(text for item in values if (text := str(item).strip()))


def _speech_duration_ms(action: Mapping[str, Any]) -> int:
    text = str(action.get("text") or "").strip()
    cjk_count = len(_CJK_PATTERN.findall(text))
    if cjk_count > len(text) * 0.3:
        raw_duration = max(2_000, len(text) * 150)
    else:
        word_count = len(text.split())
        raw_duration = max(2_000, word_count * 240)
    raw_speed = action.get("speed", 1)
    try:
        speed = float(raw_speed)
    except (TypeError, ValueError):
        speed = 1.0
    if speed <= 0:
        speed = 1.0
    return round(raw_duration / speed)


def _action_duration_ms(action: Mapping[str, Any]) -> int:
    action_type = str(action.get("type") or "")
    if action_type == "discussion" or action_type in _FOCUS_ACTIONS:
        return 0
    if action_type == "speech":
        return _speech_duration_ms(action)
    return 1_000


def _scene_kind(scene: Mapping[str, Any]) -> SceneKind | None:
    declared = str(scene.get("type") or "")
    if declared in _SCENE_KIND:
        return _SCENE_KIND[declared]
    content_type = str(_as_mapping(scene.get("content")).get("type") or "")
    return _SCENE_KIND.get(content_type)


def _question_record(question: Mapping[str, Any], *, scene_id: str) -> ManifestQuestion | None:
    question_id = str(question.get("id") or "").strip()
    if not question_id:
        return None
    knowledge_points = question.get("knowledgePointIds")
    if knowledge_points is None:
        knowledge_points = question.get("knowledge_point_ids")
    scoring = question.get("answer")
    if scoring is None:
        scoring = question.get("correctAnswer")
    return ManifestQuestion(
        question_id=question_id,
        scene_id=scene_id,
        question_type=str(question.get("type") or "unknown"),
        required=question.get("required") is not False,
        scoring_values=_string_tuple(scoring),
        knowledge_point_ids=_string_tuple(knowledge_points),
    )


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_classroom_learning_manifest(
    payload: Mapping[str, Any],
    *,
    created_at: datetime | None = None,
) -> ResourceLearningManifestRecord:
    course_id = str(payload.get("course_id") or "").strip()
    resource_id = str(payload.get("material_id") or payload.get("resource_id") or "").strip()
    resource_version = int(payload.get("version") or 0)
    if not course_id or not resource_id or resource_version <= 0:
        raise ValueError("course_id, material_id/resource_id and a positive version are required")

    manifest_scenes: list[ManifestScene] = []
    manifest_questions: list[ManifestQuestion] = []
    for raw_scene in _as_sequence(payload.get("scenes")):
        scene = _as_mapping(raw_scene)
        scene_id = str(scene.get("id") or "").strip()
        kind = _scene_kind(scene)
        if not scene_id or kind is None:
            continue

        actions = tuple(_as_mapping(item) for item in _as_sequence(scene.get("actions")))
        required_action_ids = tuple(
            action_id
            for action in actions
            if str(action.get("type") or "") != "discussion"
            if (action_id := str(action.get("id") or "").strip())
        )

        questions: list[ManifestQuestion] = []
        if kind == "exercise":
            content = _as_mapping(scene.get("content"))
            for raw_question in _as_sequence(content.get("questions")):
                question = _question_record(_as_mapping(raw_question), scene_id=scene_id)
                if question is not None:
                    questions.append(question)
                    manifest_questions.append(question)

        manifest_scenes.append(
            ManifestScene(
                scene_id=scene_id,
                kind=kind,
                expected_duration_ms=(
                    sum(_action_duration_ms(action) for action in actions)
                    if kind == "explanation"
                    else 0
                ),
                required_action_ids=required_action_ids if kind == "explanation" else (),
                required_question_ids=tuple(
                    question.question_id for question in questions if question.required
                ),
            )
        )

    content_hash = _canonical_hash(payload)
    identity = f"{course_id}:{resource_id}:{resource_version}"
    manifest_id = f"rlm_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"
    required_questions = tuple(question for question in manifest_questions if question.required)
    timestamp = created_at or datetime.now(UTC)
    return ResourceLearningManifestRecord(
        manifest_id=manifest_id,
        course_id=course_id,
        resource_id=resource_id,
        resource_version=resource_version,
        content_hash=content_hash,
        mode="completable" if required_questions else "behavior_only",
        scenes=tuple(manifest_scenes),
        questions=tuple(manifest_questions),
        created_at=timestamp.isoformat(),
    )

