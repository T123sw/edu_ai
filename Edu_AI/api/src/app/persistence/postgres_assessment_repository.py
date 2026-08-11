"""SQLAlchemy persistence for learning-task assessments."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.assessment.models import (
    AssessmentAnswerRecord,
    AssessmentAssignmentRecord,
    AssessmentAttemptRecord,
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentVersionRecord,
    utc_now,
)
from app.assessment.store import AssessmentStoreError
from app.database import (
    AssessmentAnswerModel,
    AssessmentAssignmentModel,
    AssessmentAttemptModel,
    AssessmentItemModel,
    AssessmentModel,
    AssessmentVersionModel,
    database_session,
)

from .postgres_repositories import _iso_timestamp, _timestamp


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PostgresAssessmentRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create_draft(
        self,
        assessment: AssessmentRecord,
        version: AssessmentVersionRecord,
    ) -> AssessmentVersionRecord:
        try:
            with database_session(engine=self._engine) as session:
                session.add(
                    AssessmentModel(
                        assessment_id=assessment.assessment_id,
                        course_id=assessment.course_id,
                        task_id=assessment.task_id,
                        created_by=assessment.created_by,
                        created_at=_timestamp(assessment.created_at),
                        current_version_id=assessment.current_version_id,
                    )
                )
                session.add(self._version_model(version))
        except IntegrityError as exc:
            raise AssessmentStoreError(
                "TASK_ASSESSMENT_EXISTS", "A task can have only one assessment"
            ) from exc
        return version

    def replace_draft_items(
        self,
        assessment_version_id: str,
        items: list[AssessmentItemRecord],
        *,
        expected_revision: int,
    ) -> AssessmentVersionRecord:
        with database_session(engine=self._engine) as session:
            version = session.get(AssessmentVersionModel, assessment_version_id)
            if version is None:
                raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
            if version.status != "draft":
                raise AssessmentStoreError("VERSION_IMMUTABLE", "Published versions cannot be edited")
            if version.draft_revision != int(expected_revision):
                raise AssessmentStoreError(
                    "DRAFT_REVISION_CONFLICT", "Assessment draft has changed"
                )
            session.execute(
                delete(AssessmentItemModel).where(
                    AssessmentItemModel.assessment_version_id == assessment_version_id
                )
            )
            session.add_all([self._item_model(item) for item in items])
            version.draft_revision += 1
            session.flush()
            result = self._version(version)
        return result

    def update_draft(
        self,
        record: AssessmentVersionRecord,
        items: list[AssessmentItemRecord],
        *,
        expected_revision: int,
    ) -> AssessmentVersionRecord:
        with database_session(engine=self._engine) as session:
            version = session.get(AssessmentVersionModel, record.assessment_version_id)
            if version is None:
                raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
            if version.status != "draft":
                raise AssessmentStoreError("VERSION_IMMUTABLE", "Published versions cannot be edited")
            if version.draft_revision != int(expected_revision):
                raise AssessmentStoreError("DRAFT_REVISION_CONFLICT", "Assessment draft has changed")
            version.source_mode = record.source_mode
            version.assessment_mode = record.assessment_mode
            version.pass_threshold = record.pass_threshold
            version.mastery_threshold = record.mastery_threshold
            version.max_attempts = record.max_attempts
            version.answer_reveal_policy = record.answer_reveal_policy
            version.shuffle_questions = record.shuffle_questions
            version.shuffle_options = record.shuffle_options
            version.draft_revision += 1
            session.execute(
                delete(AssessmentItemModel).where(
                    AssessmentItemModel.assessment_version_id == record.assessment_version_id
                )
            )
            session.add_all([self._item_model(item) for item in items])
            session.flush()
            result = self._version(version)
        return result

    def publish_version(
        self,
        assessment_version_id: str,
        *,
        published_by: str,
    ) -> AssessmentVersionRecord:
        with database_session(engine=self._engine) as session:
            version = session.get(AssessmentVersionModel, assessment_version_id)
            if version is None:
                raise AssessmentStoreError("VERSION_NOT_FOUND", "Assessment version was not found")
            if version.status == "published":
                return self._version(version)
            items = list(
                session.scalars(
                    select(AssessmentItemModel)
                    .where(AssessmentItemModel.assessment_version_id == assessment_version_id)
                    .order_by(AssessmentItemModel.position, AssessmentItemModel.assessment_item_id)
                ).all()
            )
            if not items:
                raise AssessmentStoreError("ASSESSMENT_EMPTY", "Assessment requires at least one item")
            version.status = "published"
            version.content_hash = self._content_hash(version, items)
            version.published_at = _timestamp(utc_now())
            version.published_by = published_by
            assessment = session.get(AssessmentModel, version.assessment_id)
            if assessment is None:
                raise AssessmentStoreError("ASSESSMENT_NOT_FOUND", "Assessment was not found")
            assessment.current_version_id = assessment_version_id
            session.flush()
            result = self._version(version)
        return result

    def get_assessment_for_task(self, course_id: str, task_id: str) -> AssessmentRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(AssessmentModel).where(
                    AssessmentModel.course_id == course_id,
                    AssessmentModel.task_id == task_id,
                )
            )
            return self._assessment(record) if record else None

    def get_version(self, assessment_version_id: str) -> AssessmentVersionRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.get(AssessmentVersionModel, assessment_version_id)
            return self._version(record) if record else None

    def get_latest_version(self, assessment_id: str) -> AssessmentVersionRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(AssessmentVersionModel)
                .where(AssessmentVersionModel.assessment_id == assessment_id)
                .order_by(AssessmentVersionModel.version_number.desc())
                .limit(1)
            )
            return self._version(record) if record else None

    def list_items(self, assessment_version_id: str) -> list[AssessmentItemRecord]:
        with database_session(engine=self._engine) as session:
            records = list(
                session.scalars(
                    select(AssessmentItemModel)
                    .where(AssessmentItemModel.assessment_version_id == assessment_version_id)
                    .order_by(AssessmentItemModel.position, AssessmentItemModel.assessment_item_id)
                ).all()
            )
            return [self._item(item) for item in records]

    def get_or_create_assignment(
        self, *, task_id: str, course_id: str, student_id: str,
        assessment_version_id: str, max_attempts: int,
    ) -> AssessmentAssignmentRecord:
        existing = self.get_assignment(
            course_id=course_id, task_id=task_id, student_id=student_id
        )
        if existing is not None:
            return existing
        record = AssessmentAssignmentRecord(
            assessment_assignment_id=f"asa_{uuid4().hex}", task_id=task_id,
            course_id=course_id, student_id=student_id,
            assessment_version_id=assessment_version_id, cycle_number=1,
            max_attempts=max_attempts,
        )
        try:
            with database_session(engine=self._engine) as session:
                session.add(AssessmentAssignmentModel(
                    assessment_assignment_id=record.assessment_assignment_id,
                    task_id=record.task_id, course_id=record.course_id,
                    student_id=record.student_id,
                    assessment_version_id=record.assessment_version_id,
                    cycle_number=record.cycle_number, max_attempts=record.max_attempts,
                    attempts_used=record.attempts_used, best_attempt_id=None,
                    best_final_score=None, result=record.result, answers_revealed_at=None,
                    created_at=_timestamp(record.created_at), updated_at=_timestamp(record.updated_at),
                ))
        except IntegrityError:
            existing = self.get_assignment(
                course_id=course_id, task_id=task_id, student_id=student_id
            )
            if existing is None:
                raise
            return existing
        return record

    def get_assignment(
        self, *, course_id: str, task_id: str, student_id: str
    ) -> AssessmentAssignmentRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(AssessmentAssignmentModel)
                .where(
                    AssessmentAssignmentModel.course_id == course_id,
                    AssessmentAssignmentModel.task_id == task_id,
                    AssessmentAssignmentModel.student_id == student_id,
                )
                .order_by(AssessmentAssignmentModel.cycle_number.desc())
                .limit(1)
            )
            return self._assignment(record) if record else None

    def create_attempt(self, assignment: AssessmentAssignmentRecord) -> AssessmentAttemptRecord:
        with database_session(engine=self._engine) as session:
            current = session.scalar(
                select(AssessmentAssignmentModel)
                .where(AssessmentAssignmentModel.assessment_assignment_id == assignment.assessment_assignment_id)
                .with_for_update()
            )
            if current is None:
                raise AssessmentStoreError("ASSIGNMENT_NOT_FOUND", "Assessment assignment was not found")
            active = session.scalar(
                select(AssessmentAttemptModel).where(
                    AssessmentAttemptModel.assessment_assignment_id == assignment.assessment_assignment_id,
                    AssessmentAttemptModel.status == "in_progress",
                )
            )
            if active is not None:
                return self._attempt(active)
            if current.attempts_used >= current.max_attempts:
                raise AssessmentStoreError("ATTEMPTS_EXHAUSTED", "No scored attempts remain")
            record = AssessmentAttemptRecord.new(
                assignment_id=assignment.assessment_assignment_id,
                assessment_version_id=assignment.assessment_version_id,
                task_id=assignment.task_id, course_id=assignment.course_id,
                student_id=assignment.student_id, attempt_number=current.attempts_used + 1,
            )
            model = self._attempt_model(record)
            session.add(model)
            session.flush()
            return self._attempt(model)

    def get_attempt(self, attempt_id: str) -> AssessmentAttemptRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.get(AssessmentAttemptModel, attempt_id)
            return self._attempt(record) if record else None

    def save_answers(
        self, attempt_id: str, student_id: str, answers: dict[str, dict], *, expected_revision: int
    ) -> AssessmentAttemptRecord:
        with database_session(engine=self._engine) as session:
            attempt = session.scalar(
                select(AssessmentAttemptModel)
                .where(AssessmentAttemptModel.attempt_id == attempt_id)
                .with_for_update()
            )
            if attempt is None or attempt.student_id != student_id:
                raise AssessmentStoreError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
            if attempt.status != "in_progress":
                raise AssessmentStoreError("ATTEMPT_IMMUTABLE", "Submitted attempts cannot be edited")
            if attempt.draft_revision != int(expected_revision):
                raise AssessmentStoreError("ATTEMPT_REVISION_CONFLICT", "Assessment attempt has changed")
            now = _timestamp(utc_now())
            for item_id, value in answers.items():
                answer = session.scalar(select(AssessmentAnswerModel).where(
                    AssessmentAnswerModel.attempt_id == attempt_id,
                    AssessmentAnswerModel.assessment_item_id == item_id,
                ))
                if answer is None:
                    answer = AssessmentAnswerModel(
                        answer_id=f"ans_{uuid4().hex}", attempt_id=attempt_id,
                        assessment_item_id=item_id, answer=value, artifact_refs=[],
                        auto_score=None, ai_suggestion=None, final_score=None,
                        review_status="ungraded", updated_at=now,
                    )
                    session.add(answer)
                else:
                    answer.answer = value
                    answer.updated_at = now
            attempt.draft_revision += 1
            attempt.updated_at = now
            session.flush()
            return self._attempt(attempt)

    def list_answers(self, attempt_id: str) -> list[AssessmentAnswerRecord]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(AssessmentAnswerModel)
                .where(AssessmentAnswerModel.attempt_id == attempt_id)
                .order_by(AssessmentAnswerModel.assessment_item_id)
            ).all()
            return [self._answer(record) for record in records]

    def finalize_attempt(
        self, attempt_id: str, *, answer_scores: dict[str, float | None],
        status: str, auto_score: float | None, final_score: float | None,
        result: str | None, idempotency_key: str,
    ) -> AssessmentAttemptRecord:
        with database_session(engine=self._engine) as session:
            attempt = session.scalar(
                select(AssessmentAttemptModel)
                .where(AssessmentAttemptModel.attempt_id == attempt_id)
                .with_for_update()
            )
            if attempt is None:
                raise AssessmentStoreError("ATTEMPT_NOT_FOUND", "Assessment attempt was not found")
            if attempt.status != "in_progress":
                return self._attempt(attempt)
            now = _timestamp(utc_now())
            for item_id, score in answer_scores.items():
                answer = session.scalar(select(AssessmentAnswerModel).where(
                    AssessmentAnswerModel.attempt_id == attempt_id,
                    AssessmentAnswerModel.assessment_item_id == item_id,
                ))
                if answer is not None:
                    answer.auto_score = score
                    answer.final_score = score
                    answer.review_status = "graded" if score is not None else "pending_review"
                    answer.updated_at = now
            attempt.status = status
            attempt.submitted_at = now
            attempt.auto_score = auto_score
            attempt.final_score = final_score
            attempt.result = result
            attempt.submission_idempotency_key = idempotency_key
            attempt.updated_at = now
            assignment = session.get(AssessmentAssignmentModel, attempt.assessment_assignment_id)
            if assignment is None:
                raise AssessmentStoreError("ASSIGNMENT_NOT_FOUND", "Assessment assignment was not found")
            assignment.attempts_used += 1
            if final_score is not None and (
                assignment.best_final_score is None or final_score > assignment.best_final_score
            ):
                assignment.best_final_score = final_score
                assignment.best_attempt_id = attempt_id
            if result in {"passed", "mastered"}:
                if assignment.result != "mastered":
                    assignment.result = result
            elif result == "pending_review" and assignment.result not in {"passed", "mastered"}:
                assignment.result = "pending_review"
            elif assignment.result == "not_attempted":
                assignment.result = "needs_retry"
            assignment.updated_at = now
            session.flush()
            return self._attempt(attempt)

    def list_attempts(self, assignment_id: str) -> list[AssessmentAttemptRecord]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(AssessmentAttemptModel)
                .where(AssessmentAttemptModel.assessment_assignment_id == assignment_id)
                .order_by(AssessmentAttemptModel.attempt_number)
            ).all()
            return [self._attempt(record) for record in records]

    def reveal_assignment_answers(
        self, assignment_id: str
    ) -> AssessmentAssignmentRecord:
        with database_session(engine=self._engine) as session:
            assignment = session.scalar(
                select(AssessmentAssignmentModel)
                .where(
                    AssessmentAssignmentModel.assessment_assignment_id == assignment_id
                )
                .with_for_update()
            )
            if assignment is None:
                raise AssessmentStoreError(
                    "ASSIGNMENT_NOT_FOUND", "Assessment assignment was not found"
                )
            now = _timestamp(utc_now())
            if assignment.answers_revealed_at is None:
                assignment.answers_revealed_at = now
            assignment.updated_at = now
            session.flush()
            return self._assignment(assignment)

    @staticmethod
    def _version_model(record: AssessmentVersionRecord) -> AssessmentVersionModel:
        return AssessmentVersionModel(
            assessment_version_id=record.assessment_version_id,
            assessment_id=record.assessment_id,
            version_number=record.version_number,
            status=record.status,
            source_mode=record.source_mode,
            assessment_mode=record.assessment_mode,
            pass_threshold=record.pass_threshold,
            mastery_threshold=record.mastery_threshold,
            max_attempts=record.max_attempts,
            score_policy=record.score_policy,
            answer_reveal_policy=record.answer_reveal_policy,
            shuffle_questions=record.shuffle_questions,
            shuffle_options=record.shuffle_options,
            draft_revision=record.draft_revision,
            content_hash=record.content_hash,
            published_at=_timestamp(record.published_at) if record.published_at else None,
            published_by=record.published_by,
            created_at=_timestamp(record.created_at),
        )

    @staticmethod
    def _item_model(record: AssessmentItemRecord) -> AssessmentItemModel:
        return AssessmentItemModel(
            assessment_item_id=record.assessment_item_id,
            assessment_version_id=record.assessment_version_id,
            position=record.position,
            item_type=record.item_type,
            prompt=record.prompt,
            scoring_key=record.scoring_key,
            rubric=record.rubric,
            max_score=record.max_score,
            grading_provider=record.grading_provider,
            knowledge_point_ids=record.knowledge_point_ids,
            source_refs=record.source_refs,
            source_exposure_state=record.source_exposure_state,
            created_origin=record.created_origin,
        )

    @staticmethod
    def _assessment(record: AssessmentModel) -> AssessmentRecord:
        return AssessmentRecord(
            assessment_id=record.assessment_id,
            course_id=record.course_id,
            task_id=record.task_id,
            created_by=record.created_by,
            created_at=_iso_timestamp(record.created_at),
            current_version_id=record.current_version_id,
        )

    @staticmethod
    def _version(record: AssessmentVersionModel) -> AssessmentVersionRecord:
        return AssessmentVersionRecord(
            assessment_version_id=record.assessment_version_id,
            assessment_id=record.assessment_id,
            version_number=record.version_number,
            status=record.status,
            source_mode=record.source_mode,
            assessment_mode=record.assessment_mode,
            pass_threshold=record.pass_threshold,
            mastery_threshold=record.mastery_threshold,
            max_attempts=record.max_attempts,
            score_policy=record.score_policy,
            answer_reveal_policy=record.answer_reveal_policy,
            shuffle_questions=record.shuffle_questions,
            shuffle_options=record.shuffle_options,
            draft_revision=record.draft_revision,
            content_hash=record.content_hash,
            published_at=_iso_timestamp(record.published_at) if record.published_at else None,
            published_by=record.published_by,
            created_at=_iso_timestamp(record.created_at),
        )

    @staticmethod
    def _item(record: AssessmentItemModel) -> AssessmentItemRecord:
        return AssessmentItemRecord(
            assessment_item_id=record.assessment_item_id,
            assessment_version_id=record.assessment_version_id,
            position=record.position,
            item_type=record.item_type,
            prompt=dict(record.prompt or {}),
            scoring_key=dict(record.scoring_key or {}),
            rubric=dict(record.rubric or {}),
            max_score=record.max_score,
            grading_provider=record.grading_provider,
            knowledge_point_ids=list(record.knowledge_point_ids or []),
            source_refs=list(record.source_refs or []),
            source_exposure_state=record.source_exposure_state,
            created_origin=record.created_origin,
        )

    @staticmethod
    def _attempt_model(record: AssessmentAttemptRecord) -> AssessmentAttemptModel:
        return AssessmentAttemptModel(
            attempt_id=record.attempt_id, assessment_assignment_id=record.assignment_id,
            assessment_version_id=record.assessment_version_id, task_id=record.task_id,
            course_id=record.course_id, student_id=record.student_id,
            attempt_number=record.attempt_number, status=record.status,
            draft_revision=record.draft_revision, submitted_at=None, auto_score=None,
            final_score=None, result=None, invalidated_at=None, invalidated_by=None,
            submission_idempotency_key=None,
            invalidation_reason=None, created_at=_timestamp(record.created_at),
            updated_at=_timestamp(record.updated_at),
        )

    @staticmethod
    def _assignment(record: AssessmentAssignmentModel) -> AssessmentAssignmentRecord:
        return AssessmentAssignmentRecord(
            assessment_assignment_id=record.assessment_assignment_id,
            task_id=record.task_id, course_id=record.course_id, student_id=record.student_id,
            assessment_version_id=record.assessment_version_id,
            cycle_number=record.cycle_number, max_attempts=record.max_attempts,
            attempts_used=record.attempts_used, best_attempt_id=record.best_attempt_id,
            best_final_score=record.best_final_score, result=record.result,
            answers_revealed_at=_iso_timestamp(record.answers_revealed_at) if record.answers_revealed_at else None,
            created_at=_iso_timestamp(record.created_at), updated_at=_iso_timestamp(record.updated_at),
        )

    @staticmethod
    def _attempt(record: AssessmentAttemptModel) -> AssessmentAttemptRecord:
        return AssessmentAttemptRecord(
            attempt_id=record.attempt_id, assignment_id=record.assessment_assignment_id,
            assessment_version_id=record.assessment_version_id, task_id=record.task_id,
            course_id=record.course_id, student_id=record.student_id,
            attempt_number=record.attempt_number, status=record.status,
            draft_revision=record.draft_revision,
            submitted_at=_iso_timestamp(record.submitted_at) if record.submitted_at else None,
            auto_score=record.auto_score, final_score=record.final_score, result=record.result,
            submission_idempotency_key=record.submission_idempotency_key,
            invalidated_at=_iso_timestamp(record.invalidated_at) if record.invalidated_at else None,
            invalidated_by=record.invalidated_by, invalidation_reason=record.invalidation_reason,
            created_at=_iso_timestamp(record.created_at), updated_at=_iso_timestamp(record.updated_at),
        )

    @staticmethod
    def _answer(record: AssessmentAnswerModel) -> AssessmentAnswerRecord:
        return AssessmentAnswerRecord(
            answer_id=record.answer_id, attempt_id=record.attempt_id,
            assessment_item_id=record.assessment_item_id, answer=dict(record.answer or {}),
            artifact_refs=list(record.artifact_refs or []), auto_score=record.auto_score,
            ai_suggestion=dict(record.ai_suggestion) if record.ai_suggestion else None,
            final_score=record.final_score, review_status=record.review_status,
            updated_at=_iso_timestamp(record.updated_at),
        )

    @staticmethod
    def _content_hash(
        version: AssessmentVersionModel,
        items: list[AssessmentItemModel],
    ) -> str:
        payload = {
            "settings": {
                "assessment_mode": version.assessment_mode,
                "pass_threshold": version.pass_threshold,
                "mastery_threshold": version.mastery_threshold,
                "max_attempts": version.max_attempts,
                "score_policy": version.score_policy,
                "answer_reveal_policy": version.answer_reveal_policy,
                "shuffle_questions": version.shuffle_questions,
                "shuffle_options": version.shuffle_options,
            },
            "items": [
                {
                    "assessment_item_id": item.assessment_item_id,
                    "position": item.position,
                    "item_type": item.item_type,
                    "prompt": item.prompt,
                    "scoring_key": item.scoring_key,
                    "rubric": item.rubric,
                    "max_score": item.max_score,
                    "grading_provider": item.grading_provider,
                    "knowledge_point_ids": item.knowledge_point_ids,
                    "source_refs": item.source_refs,
                    "source_exposure_state": item.source_exposure_state,
                    "created_origin": item.created_origin,
                }
                for item in items
            ],
        }
        return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
