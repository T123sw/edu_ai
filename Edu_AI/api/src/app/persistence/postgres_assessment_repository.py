"""SQLAlchemy persistence for learning-task assessments."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.assessment.models import (
    AssessmentItemRecord,
    AssessmentRecord,
    AssessmentVersionRecord,
    utc_now,
)
from app.assessment.store import AssessmentStoreError
from app.database import (
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
