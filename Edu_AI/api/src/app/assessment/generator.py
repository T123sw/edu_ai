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
        if not coverage_gaps:
            return []
        context = "\n\n".join(
            f"材料：{_text(material.get('title')) or _text(material.get('material_id'))}\n{text}"
            for material, text in sources
        )
        generator = QuizGenerator(llm=self.llm)
        artifact = generator.generate(
            preparation={
                "topic": task_title,
                "question_count": len(coverage_gaps),
                "question_types": ["choice", "short"],
                "difficulty": difficulty,
                "knowledge_points": coverage_gaps,
                "weak_points": [],
                "source_scope": ["selected_course_materials"],
            },
            context_summary=f"{task_instructions}\n{context}",
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
        for index, raw in enumerate(questions[: len(coverage_gaps)]):
            if not isinstance(raw, dict):
                continue
            item = normalize_question(
                raw,
                assessment_version_id=assessment_version_id,
                position=index + 1,
                knowledge_point_ids=[coverage_gaps[index]],
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
