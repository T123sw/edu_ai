"""Teacher authoring and publication orchestration for task assessments."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Callable
from uuid import uuid4

from app.learning.service import LearningRuleError, LearningService

from .extractors import extract_assessment_items
from .models import AssessmentRecord, AssessmentVersionRecord
from .models import AssessmentItemRecord
from .policies import (
    AssessmentPolicyError,
    can_reveal_answers,
    grade_objective_item,
    validate_settings,
)
from .quality import AssessmentQualityService, QualityReport
from .store import AssessmentStore, AssessmentStoreError


MaterialLookup = Callable[[str, str, str, str], dict[str, Any] | None]


class AssessmentRuleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AssessmentService:
    def __init__(
        self,
        *,
        store: AssessmentStore,
        learning_service: LearningService,
        material_lookup: MaterialLookup,
        generator=None,
    ):
        self.store = store
        self.learning_service = learning_service
        self.material_lookup = material_lookup
        self.generator = generator
        self.quality_service = AssessmentQualityService()

    def _teacher_task(self, *, course_id: str, task_id: str, teacher_id: str):
        try:
            self.learning_service._teacher_membership(
                course_id=course_id, teacher_id=teacher_id
            )
            return self.learning_service._task_or_error(
                course_id=course_id, task_id=task_id
            )
        except LearningRuleError as error:
            raise AssessmentRuleError(error.code, error.message) from error

    def _materials(self, task, teacher_id: str) -> list[dict[str, Any]]:
        materials = []
        for ref in task.resource_refs:
            material = self.material_lookup(
                task.course_id,
                ref["material_type"],
                ref["material_id"],
                teacher_id,
            )
            if material and str(material.get("visibility", "")) == "course":
                materials.append(
                    {
                        **material,
                        "material_type": ref["material_type"],
                        "material_id": ref["material_id"],
                    }
                )
        return materials

    def detect_or_create_draft(
        self, *, course_id: str, task_id: str, teacher_id: str
    ) -> dict[str, Any]:
        task = self._teacher_task(
            course_id=course_id, task_id=task_id, teacher_id=teacher_id
        )
        existing = self.store.get_assessment_for_task(course_id, task_id)
        if existing is not None:
            version = self.store.get_latest_version(existing.assessment_id)
            if version is None:
                raise AssessmentRuleError(
                    "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
                )
            return self._draft_payload(task, version)

        assessment_id = f"asmt_{uuid4().hex}"
        version_id = f"asv_{uuid4().hex}"
        materials = self._materials(task, teacher_id)
        extracted = extract_assessment_items(
            materials,
            assessment_version_id=version_id,
            knowledge_point_ids=list(task.knowledge_point_ids),
        ).items
        assessment = AssessmentRecord(
            assessment_id=assessment_id,
            course_id=course_id,
            task_id=task_id,
            created_by=teacher_id,
        )
        version = AssessmentVersionRecord(
            assessment_version_id=version_id,
            assessment_id=assessment_id,
            version_number=1,
            status="draft",
            source_mode="imported" if extracted else "manual",
            assessment_mode="closed_book",
            pass_threshold=60,
            mastery_threshold=80,
            max_attempts=3,
            score_policy="best_final_score",
            answer_reveal_policy="after_finish_or_exhausted",
            shuffle_questions=False,
            shuffle_options=False,
        )
        try:
            self.store.create_draft(assessment, version)
            version = self.store.replace_draft_items(
                version_id, extracted, expected_revision=0
            )
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        return self._draft_payload(task, version)

    def get_task_draft(
        self, *, course_id: str, task_id: str, teacher_id: str
    ) -> dict[str, Any]:
        task = self._teacher_task(
            course_id=course_id, task_id=task_id, teacher_id=teacher_id
        )
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Task assessment is required")
        version = self.store.get_latest_version(assessment.assessment_id)
        if version is None:
            raise AssessmentRuleError(
                "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
            )
        return self._draft_payload(task, version)

    def validate_task_assessment(
        self, *, course_id: str, task_id: str, teacher_id: str
    ) -> QualityReport:
        task = self._teacher_task(
            course_id=course_id, task_id=task_id, teacher_id=teacher_id
        )
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Task assessment is required")
        version = self.store.get_latest_version(assessment.assessment_id)
        if version is None:
            raise AssessmentRuleError(
                "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
            )
        return self.quality_service.validate(
            self.store.list_items(version.assessment_version_id),
            required_knowledge_point_ids=list(task.knowledge_point_ids),
        )

    def update_task_draft(
        self,
        *,
        course_id: str,
        task_id: str,
        teacher_id: str,
        expected_revision: int,
        settings: dict[str, Any],
        raw_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        task = self._teacher_task(
            course_id=course_id, task_id=task_id, teacher_id=teacher_id
        )
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Task assessment is required")
        version = self.store.get_latest_version(assessment.assessment_id)
        if version is None:
            raise AssessmentRuleError(
                "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
            )
        try:
            validated = validate_settings(
                settings["pass_threshold"],
                settings["mastery_threshold"],
                settings["max_attempts"],
            )
        except AssessmentPolicyError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        assessment_mode = str(settings["assessment_mode"])
        if assessment_mode not in {"closed_book", "open_book"}:
            raise AssessmentRuleError("INVALID_ASSESSMENT_SETTINGS", "Invalid assessment mode")
        reveal_policy = str(settings["answer_reveal_policy"])
        if reveal_policy not in {"after_finish_or_exhausted", "after_each_attempt", "never"}:
            raise AssessmentRuleError("INVALID_ASSESSMENT_SETTINGS", "Invalid answer reveal policy")
        updated_version = replace(
            version,
            assessment_mode=assessment_mode,
            pass_threshold=validated.pass_threshold,
            mastery_threshold=validated.mastery_threshold,
            max_attempts=validated.max_attempts,
            answer_reveal_policy=reveal_policy,
            shuffle_questions=bool(settings["shuffle_questions"]),
            shuffle_options=bool(settings["shuffle_options"]),
        )
        items = []
        for position, raw in enumerate(raw_items, start=1):
            items.append(
                AssessmentItemRecord(
                    assessment_item_id=str(raw["assessment_item_id"]),
                    assessment_version_id=version.assessment_version_id,
                    position=position,
                    item_type=str(raw["item_type"]),
                    prompt=dict(raw.get("prompt") or {}),
                    scoring_key=dict(raw.get("scoring_key") or {}),
                    rubric=dict(raw.get("rubric") or {}),
                    max_score=float(raw.get("max_score") or 0),
                    grading_provider=str(raw["grading_provider"]),
                    knowledge_point_ids=list(raw.get("knowledge_point_ids") or []),
                    source_refs=list(raw.get("source_refs") or []),
                    source_exposure_state=str(raw.get("source_exposure_state") or "private"),
                    created_origin=str(raw.get("created_origin") or "manual"),
                )
            )
        try:
            updated_version = self.store.update_draft(
                updated_version, items, expected_revision=expected_revision
            )
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        return self._draft_payload(task, updated_version)

    def generate_missing_items(
        self,
        *,
        course_id: str,
        task_id: str,
        teacher_id: str,
        expected_revision: int,
        difficulty: str,
    ) -> dict[str, Any]:
        task = self._teacher_task(
            course_id=course_id, task_id=task_id, teacher_id=teacher_id
        )
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Task assessment is required")
        version = self.store.get_latest_version(assessment.assessment_id)
        if version is None:
            raise AssessmentRuleError(
                "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
            )
        existing = self.store.list_items(version.assessment_version_id)
        covered = {point for item in existing for point in item.knowledge_point_ids}
        gaps = [point for point in task.knowledge_point_ids if point not in covered]
        if not gaps:
            return self._draft_payload(task, version)
        generator = self.generator
        if generator is None:
            from .generator import AssessmentDraftGenerator

            generator = AssessmentDraftGenerator()
        try:
            generated = generator.generate(
                materials=self._materials(task, teacher_id),
                assessment_version_id=version.assessment_version_id,
                task_title=task.title,
                task_instructions=task.instructions,
                coverage_gaps=gaps,
                difficulty=difficulty,
            )
            combined = existing + [
                replace(item, position=len(existing) + index)
                for index, item in enumerate(generated, start=1)
            ]
            source_mode = "mixed" if existing else "generated"
            version = self.store.update_draft(
                replace(version, source_mode=source_mode),
                combined,
                expected_revision=expected_revision,
            )
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        except ValueError as error:
            code = str(getattr(error, "code", "ASSESSMENT_GENERATION_FAILED"))
            message = str(getattr(error, "message", "Assessment generation failed"))
            raise AssessmentRuleError(code, message) from error
        return self._draft_payload(task, version)

    def publish_task(
        self,
        *,
        course_id: str,
        task_id: str,
        teacher_id: str,
        expected_revision: int | None = None,
    ):
        task = self._teacher_task(
            course_id=course_id, task_id=task_id, teacher_id=teacher_id
        )
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Task assessment is required")
        version = self.store.get_latest_version(assessment.assessment_id)
        if version is None:
            raise AssessmentRuleError(
                "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
            )
        if expected_revision is not None and version.draft_revision != expected_revision:
            raise AssessmentRuleError(
                "DRAFT_REVISION_CONFLICT", "Assessment draft has changed"
            )
        report = self.quality_service.validate(
            self.store.list_items(version.assessment_version_id),
            required_knowledge_point_ids=list(task.knowledge_point_ids),
        )
        if not report.publishable:
            raise AssessmentRuleError(
                "ASSESSMENT_INVALID", "Task assessment must pass validation before publication"
            )
        try:
            self.store.publish_version(
                version.assessment_version_id, published_by=teacher_id
            )
            return self.learning_service.publish_task(
                course_id=course_id, task_id=task_id, teacher_id=teacher_id
            )
        except (AssessmentStoreError, LearningRuleError) as error:
            raise AssessmentRuleError(error.code, error.message) from error

    def start_attempt(self, *, course_id: str, task_id: str, student_id: str):
        try:
            self.learning_service._course_read_membership(
                course_id=course_id, user_id=student_id
            )
            task = self.learning_service._task_or_error(course_id=course_id, task_id=task_id)
        except LearningRuleError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        if task.status != "published":
            raise AssessmentRuleError("TASK_NOT_PUBLISHED", "Learning task is not published")
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None or assessment.current_version_id is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Published assessment is required")
        version = self.store.get_version(assessment.current_version_id)
        if version is None or version.status != "published":
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Published assessment is required")
        assignment = self.store.get_or_create_assignment(
            task_id=task_id,
            course_id=course_id,
            student_id=student_id,
            assessment_version_id=version.assessment_version_id,
            max_attempts=version.max_attempts,
        )
        if assignment.answers_revealed_at is not None:
            raise AssessmentRuleError("ANSWERS_REVEALED", "Scored attempts are closed")
        try:
            return self.store.create_attempt(assignment)
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error

    def get_student_assessment(
        self, *, course_id: str, task_id: str, student_id: str
    ) -> dict[str, Any]:
        try:
            self.learning_service._course_read_membership(
                course_id=course_id, user_id=student_id
            )
            task = self.learning_service._task_or_error(course_id=course_id, task_id=task_id)
        except LearningRuleError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        if task.status != "published":
            raise AssessmentRuleError("TASK_NOT_PUBLISHED", "Learning task is not published")
        assessment = self.store.get_assessment_for_task(course_id, task_id)
        if assessment is None or assessment.current_version_id is None:
            raise AssessmentRuleError("ASSESSMENT_REQUIRED", "Published assessment is required")
        version = self.store.get_version(assessment.current_version_id)
        if version is None:
            raise AssessmentRuleError("ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found")
        items = self.store.list_items(version.assessment_version_id)
        return {
            "assessment_version_id": version.assessment_version_id,
            "task_id": task_id,
            "assessment_mode": version.assessment_mode,
            "max_attempts": version.max_attempts,
            "items": [
                {
                    "assessment_item_id": item.assessment_item_id,
                    "position": item.position,
                    "item_type": item.item_type,
                    "prompt": item.prompt,
                    "max_score": item.max_score,
                    "knowledge_point_ids": item.knowledge_point_ids,
                }
                for item in items
            ],
        }
    def save_answers(
        self,
        *,
        attempt_id: str,
        student_id: str,
        answers: dict[str, dict[str, Any]],
        expected_revision: int,
        course_id: str | None = None,
        task_id: str | None = None,
    ):
        attempt = self.store.get_attempt(attempt_id)
        if (
            attempt is None
            or attempt.student_id != student_id
            or (course_id is not None and attempt.course_id != course_id)
            or (task_id is not None and attempt.task_id != task_id)
        ):
            raise AssessmentRuleError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
        allowed_item_ids = {
            item.assessment_item_id
            for item in self.store.list_items(attempt.assessment_version_id)
        }
        if not set(answers).issubset(allowed_item_ids):
            raise AssessmentRuleError(
                "INVALID_ANSWER_ITEM", "Answer contains an item outside this assessment"
            )
        try:
            return self.store.save_answers(
                attempt_id, student_id, answers, expected_revision=expected_revision
            )
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error

    def submit_attempt(
        self,
        *,
        attempt_id: str,
        student_id: str,
        idempotency_key: str,
        course_id: str | None = None,
        task_id: str | None = None,
    ):
        if not str(idempotency_key).strip():
            raise AssessmentRuleError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required")
        attempt = self.store.get_attempt(attempt_id)
        if (
            attempt is None
            or attempt.student_id != student_id
            or (course_id is not None and attempt.course_id != course_id)
            or (task_id is not None and attempt.task_id != task_id)
        ):
            raise AssessmentRuleError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
        if attempt.status != "in_progress":
            self._sync_verified_outcome(attempt)
            return attempt
        items = self.store.list_items(attempt.assessment_version_id)
        answers = {item.assessment_item_id: item for item in self.store.list_answers(attempt_id)}
        answer_scores: dict[str, float | None] = {}
        total_score = 0.0
        maximum = sum(item.max_score for item in items)
        pending_review = False
        for item in items:
            answer = answers.get(item.assessment_item_id)
            grade = grade_objective_item(item, answer.answer if answer else {})
            answer_scores[item.assessment_item_id] = grade.final_score
            if grade.final_score is None:
                pending_review = True
            else:
                total_score += grade.final_score
        version = self.store.get_version(attempt.assessment_version_id)
        if version is None:
            raise AssessmentRuleError("ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found")
        percentage = round(total_score / maximum * 100, 2) if maximum > 0 else 0.0
        if pending_review:
            status = "pending_review"
            final_score = None
            result = "pending_review"
        else:
            status = "graded"
            final_score = percentage
            result = (
                "mastered" if percentage >= version.mastery_threshold
                else "passed" if percentage >= version.pass_threshold
                else "needs_retry"
            )
        try:
            finalized = self.store.finalize_attempt(
                attempt_id,
                answer_scores=answer_scores,
                status=status,
                auto_score=percentage,
                final_score=final_score,
                result=result,
                idempotency_key=idempotency_key,
            )
            self._sync_verified_outcome(finalized)
            return finalized
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error

    def _sync_verified_outcome(self, attempt) -> None:
        if attempt.result not in {"passed", "mastered"} or attempt.final_score is None:
            return
        try:
            self.learning_service.record_verified_assessment_outcome(
                outcome_id=attempt.attempt_id,
                course_id=attempt.course_id,
                task_id=attempt.task_id,
                student_id=attempt.student_id,
                score=attempt.final_score,
            )
        except LearningRuleError as error:
            raise AssessmentRuleError(error.code, error.message) from error

    def get_student_assignment(
        self, *, course_id: str, task_id: str, student_id: str
    ):
        try:
            self.learning_service._course_read_membership(
                course_id=course_id, user_id=student_id
            )
        except LearningRuleError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        assignment = self.store.get_assignment(
            course_id=course_id, task_id=task_id, student_id=student_id
        )
        if assignment is None:
            raise AssessmentRuleError("ASSIGNMENT_NOT_FOUND", "Assessment assignment was not found")
        return assignment

    def list_student_attempts(
        self, *, course_id: str, task_id: str, student_id: str
    ):
        assignment = self.get_student_assignment(
            course_id=course_id, task_id=task_id, student_id=student_id
        )
        return self.store.list_attempts(assignment.assessment_assignment_id)

    def get_student_feedback(
        self, *, course_id: str, task_id: str, student_id: str
    ) -> dict[str, Any]:
        assignment = self.get_student_assignment(
            course_id=course_id, task_id=task_id, student_id=student_id
        )
        return self._student_feedback_payload(assignment)

    def reveal_answers(
        self, *, course_id: str, task_id: str, student_id: str
    ) -> dict[str, Any]:
        assignment = self.get_student_assignment(
            course_id=course_id, task_id=task_id, student_id=student_id
        )
        version = self.store.get_version(assignment.assessment_version_id)
        if version is None:
            raise AssessmentRuleError(
                "ASSESSMENT_VERSION_NOT_FOUND", "Assessment version was not found"
            )
        try:
            allowed = can_reveal_answers(
                result=assignment.result,
                attempts_used=assignment.attempts_used,
                max_attempts=assignment.max_attempts,
                reveal_policy=version.answer_reveal_policy,
            )
        except AssessmentPolicyError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        if not allowed:
            raise AssessmentRuleError(
                "ANSWER_REVEAL_NOT_ALLOWED",
                "Answers can only be revealed after passing or exhausting attempts",
            )
        try:
            assignment = self.store.reveal_assignment_answers(
                assignment.assessment_assignment_id
            )
        except AssessmentStoreError as error:
            raise AssessmentRuleError(error.code, error.message) from error
        return self._student_feedback_payload(assignment)

    def _student_feedback_payload(self, assignment) -> dict[str, Any]:
        revealed = assignment.answers_revealed_at is not None
        items = self.store.list_items(assignment.assessment_version_id)
        best_answers = {
            answer.assessment_item_id: answer
            for answer in self.store.list_answers(assignment.best_attempt_id)
        } if assignment.best_attempt_id else {}
        payload_items = []
        for item in items:
            answer = best_answers.get(item.assessment_item_id)
            payload = {
                "assessment_item_id": item.assessment_item_id,
                "position": item.position,
                "item_type": item.item_type,
                "prompt": item.prompt,
                "answer": answer.answer if answer else None,
                "final_score": answer.final_score if answer else None,
                "max_score": item.max_score,
                "review_status": answer.review_status if answer else "ungraded",
            }
            if revealed:
                payload["solution"] = dict(item.scoring_key)
                if item.rubric:
                    payload["rubric"] = dict(item.rubric)
            payload_items.append(payload)
        return {
            "assessment_assignment_id": assignment.assessment_assignment_id,
            "task_id": assignment.task_id,
            "attempts_used": assignment.attempts_used,
            "max_attempts": assignment.max_attempts,
            "best_final_score": assignment.best_final_score,
            "result": assignment.result,
            "answers_revealed_at": assignment.answers_revealed_at,
            "items": payload_items,
        }

    def _draft_payload(self, task, version: AssessmentVersionRecord) -> dict[str, Any]:
        items = self.store.list_items(version.assessment_version_id)
        quality = self.quality_service.validate(
            items, required_knowledge_point_ids=list(task.knowledge_point_ids)
        )
        return {
            **asdict(version),
            "task_id": task.task_id,
            "course_id": task.course_id,
            "items": [asdict(item) for item in items],
            "quality": {
                "publishable": quality.publishable,
                "issues": [asdict(issue) for issue in quality.issues],
            },
        }
