"""Publication quality gates for assessment drafts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .models import AssessmentItemRecord


@dataclass(frozen=True)
class QualityIssue:
    code: str
    assessment_item_id: str | None
    message: str


@dataclass(frozen=True)
class QualityReport:
    publishable: bool
    issues: list[QualityIssue]


class AssessmentQualityService:
    _LEAK_KEYS = {"answer", "correct_answer", "scoring_key", "explanation", "analysis"}

    def validate(
        self,
        items: list[AssessmentItemRecord],
        *,
        required_knowledge_point_ids: list[str],
    ) -> QualityReport:
        issues: list[QualityIssue] = []
        seen_stems: dict[str, str] = {}
        covered: set[str] = set()
        for item in items:
            covered.update(item.knowledge_point_ids)
            if item.grading_provider == "deterministic" and not item.scoring_key:
                issues.append(self._issue("MISSING_SCORING_KEY", item, "Objective item has no scoring key"))
            if item.grading_provider == "rubric_ai_teacher" and not item.rubric:
                issues.append(self._issue("MISSING_RUBRIC", item, "Subjective item has no rubric"))
            if not item.source_refs:
                issues.append(self._issue("SOURCE_MISSING", item, "Assessment item has no source"))
            if self._contains_leak(item.prompt):
                issues.append(
                    self._issue("STUDENT_PROJECTION_LEAK", item, "Student prompt contains private scoring fields")
                )
            stem = str(item.prompt.get("stem") or "").strip().casefold()
            if stem and stem in seen_stems:
                issues.append(self._issue("DUPLICATE_ITEM", item, "Assessment contains duplicate prompts"))
            elif stem:
                seen_stems[stem] = item.assessment_item_id
        for knowledge_point_id in required_knowledge_point_ids:
            if knowledge_point_id not in covered:
                issues.append(
                    QualityIssue(
                        code="KNOWLEDGE_POINT_UNCOVERED",
                        assessment_item_id=None,
                        message=f"Knowledge point is not assessed: {knowledge_point_id}",
                    )
                )
        if not items:
            issues.append(QualityIssue("ASSESSMENT_EMPTY", None, "Assessment has no items"))
        return QualityReport(publishable=not issues, issues=issues)

    @staticmethod
    def _issue(code: str, item: AssessmentItemRecord, message: str) -> QualityIssue:
        return QualityIssue(code=code, assessment_item_id=item.assessment_item_id, message=message)

    def _contains_leak(self, value: Any) -> bool:
        if isinstance(value, dict):
            return any(str(key).casefold() in self._LEAK_KEYS or self._contains_leak(item) for key, item in value.items())
        if isinstance(value, list):
            return any(self._contains_leak(item) for item in value)
        json.dumps(value, ensure_ascii=False, default=str)
        return False
