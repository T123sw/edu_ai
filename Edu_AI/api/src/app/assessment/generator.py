"""Grounded assessment draft generation from selected course materials."""

from __future__ import annotations

from typing import Any

from app.chat.workflows.quiz.generator import QuizGenerator

from .extractors import normalize_question
from .models import AssessmentItemRecord


class AssessmentAuthoringError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _text(value: Any) -> str:
    return str(value or "").strip()


def _material_text(material: dict[str, Any]) -> str:
    for key in ("content", "final_markdown", "markdown", "report_content", "text", "summary"):
        value = material.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    main_content = material.get("mainContent")
    if isinstance(main_content, list):
        parts = []
        for item in main_content:
            if isinstance(item, dict):
                parts.extend([_text(item.get("title")), _text(item.get("content"))])
        return "\n".join(value for value in parts if value)
    return ""


class AssessmentDraftGenerator:
    def __init__(self, *, llm=None):
        if llm is None:
            from app.chat.agents.report_generation import get_fallback_llm

            llm = get_fallback_llm()
        self.llm = llm

    def generate(
        self,
        *,
        materials: list[dict[str, Any]],
        assessment_version_id: str,
        task_title: str,
        task_instructions: str,
        coverage_gaps: list[str],
        difficulty: str,
    ) -> list[AssessmentItemRecord]:
        sources = [
            (material, _material_text(material))
            for material in materials
            if _material_text(material)
        ]
        if not sources:
            raise AssessmentAuthoringError(
                "ASSESSMENT_SOURCE_REQUIRED",
                "Automatic assessment generation requires parseable course material",
            )
        question_count = len(coverage_gaps) if coverage_gaps else 5
        context = "\n\n".join(
            f"材料：{_text(material.get('title')) or _text(material.get('material_id'))}\n{text}"
            for material, text in sources
        )
        topic = task_title or _text(sources[0][0].get("title")) or "selected learning materials"
        generator = QuizGenerator(llm=self.llm)
        artifact = generator.generate(
            preparation={
                "topic": topic,
                "question_count": question_count,
                "question_types": [
                    "choice",
                    "short",
                    "code_trace",
                    "debug_fix",
                    "code_implementation",
                ],
                "difficulty": difficulty,
                "knowledge_points": coverage_gaps,
                "weak_points": [],
                "source_scope": ["selected_course_materials"],
            },
            context_summary=(
                f"Optional task instructions: {task_instructions or '(not provided)'}\n"
                f"The selected learning materials are the authoritative source. Infer the assessment focus, "
                f"knowledge points, and appropriate question mix from them.\n{context}"
            ),
            conversation_id=f"assessment-{assessment_version_id}",
            owner=None,
            allow_rag=False,
            selected_doc_ids=[],
        )
        content = artifact.get("content") if isinstance(artifact.get("content"), dict) else {}
        questions = list(content.get("questions") or [])
        source_refs = [
            {
                "material_type": _text(material.get("material_type")),
                "material_id": _text(material.get("material_id")),
            }
            for material, _ in sources
        ]
        items: list[AssessmentItemRecord] = []
        for index, raw in enumerate(questions[:question_count]):
            if not isinstance(raw, dict):
                continue
            raw_points = raw.get("knowledge_points") or raw.get("knowledge_point_ids") or []
            inferred_points = [
                _text(item)
                for item in (raw_points if isinstance(raw_points, list) else [raw_points])
                if _text(item)
            ]
            item = normalize_question(
                raw,
                assessment_version_id=assessment_version_id,
                position=index + 1,
                knowledge_point_ids=(
                    [coverage_gaps[index]]
                    if index < len(coverage_gaps)
                    else list(dict.fromkeys(inferred_points))[:3]
                ),
                source_ref={
                    **source_refs[0],
                    "source_item_id": _text(raw.get("id")) or f"generated-{index + 1}",
                },
                created_origin="generated",
            )
            if len(source_refs) > 1:
                item = type(item)(**{**item.__dict__, "source_refs": source_refs})
            items.append(item)
        return items
