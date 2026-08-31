from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from app.database.models import (
    ResourceLearningCoverageModel,
    ResourceLearningEventModel,
    ResourceLearningManifestModel,
    ResourceLearningProgressModel,
    ResourceLearningSessionModel,
    ResourceQuestionAttemptModel,
)
from app.database.session import database_session

from .intervals import coverage_percent, covered_duration_ms, merge_covered_ranges
from .models import (
    ManifestQuestion,
    ManifestScene,
    ResourceLearningManifestRecord,
    ResourceLearningProgressRecord,
    ResourceLearningSessionRecord,
)


def _timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _answer_values(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(sorted(str(item).strip() for item in value if str(item).strip()))
    text = str(value).strip()
    return (text,) if text else ()


class ResourceLearningRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def freeze_manifest(
        self, manifest: ResourceLearningManifestRecord
    ) -> ResourceLearningManifestRecord:
        with database_session(engine=self._engine) as session:
            existing = session.scalar(
                select(ResourceLearningManifestModel).where(
                    ResourceLearningManifestModel.course_id == manifest.course_id,
                    ResourceLearningManifestModel.resource_id == manifest.resource_id,
                    ResourceLearningManifestModel.resource_version == manifest.resource_version,
                )
            )
            if existing is not None:
                if existing.content_hash != manifest.content_hash:
                    raise ValueError("published learning manifest is immutable")
                return self._manifest(existing)
            record = ResourceLearningManifestModel(
                manifest_id=manifest.manifest_id,
                course_id=manifest.course_id,
                resource_id=manifest.resource_id,
                resource_version=manifest.resource_version,
                content_hash=manifest.content_hash,
                mode=manifest.mode,
                manifest_json={
                    "scenes": [asdict(item) for item in manifest.scenes],
                    "questions": [asdict(item) for item in manifest.questions],
                },
                created_at=_timestamp(manifest.created_at),
            )
            session.add(record)
            session.flush()
            return self._manifest(record)

    def get_manifest(
        self, course_id: str, resource_id: str, resource_version: int
    ) -> ResourceLearningManifestRecord | None:
        with database_session(engine=self._engine) as session:
            record = self._manifest_query(
                session, course_id, resource_id, resource_version
            )
            return self._manifest(record) if record is not None else None

    def start_session(
        self,
        *,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
        now: datetime,
    ) -> ResourceLearningSessionRecord:
        with database_session(engine=self._engine) as session:
            active = session.scalars(
                select(ResourceLearningSessionModel).where(
                    ResourceLearningSessionModel.student_id == student_id,
                    ResourceLearningSessionModel.course_id == course_id,
                    ResourceLearningSessionModel.resource_id == resource_id,
                    ResourceLearningSessionModel.resource_version == resource_version,
                    ResourceLearningSessionModel.status == "active",
                )
            ).all()
            for previous in active:
                previous.status = "ended"
                previous.ended_at = now

            record = ResourceLearningSessionModel(
                session_id=f"rls_{uuid4().hex}",
                course_id=course_id,
                resource_id=resource_id,
                resource_version=resource_version,
                student_id=student_id,
                status="active",
                started_at=now,
            )
            session.add(record)
            self._ensure_progress(
                session,
                course_id=course_id,
                resource_id=resource_id,
                resource_version=resource_version,
                student_id=student_id,
                now=now,
            )
            session.flush()
            return self._session(record)

    def get_session(self, session_id: str) -> ResourceLearningSessionRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.get(ResourceLearningSessionModel, session_id)
            return self._session(record) if record is not None else None

    def record_events(
        self,
        *,
        session_id: str,
        student_id: str,
        events: Sequence[Mapping[str, Any]],
        now: datetime,
    ) -> ResourceLearningProgressRecord:
        with database_session(engine=self._engine) as session:
            learning_session = session.get(ResourceLearningSessionModel, session_id)
            if learning_session is None:
                raise KeyError(session_id)
            if learning_session.student_id != student_id:
                raise PermissionError("session owner mismatch")
            if learning_session.status != "active":
                raise ValueError("session is not active")
            created_any = False
            for event in events:
                event_id = str(event["event_id"])
                sequence_number = int(event["sequence_number"])
                existing = session.get(ResourceLearningEventModel, event_id)
                if existing is not None:
                    if existing.session_id != session_id:
                        raise ValueError("event id is already used by another session")
                    continue
                collision = session.scalar(
                    select(ResourceLearningEventModel.event_id).where(
                        ResourceLearningEventModel.session_id == session_id,
                        ResourceLearningEventModel.sequence_number == sequence_number,
                    )
                )
                if collision is not None:
                    raise ValueError("sequence number is already used")
                last_sequence = session.scalar(
                    select(func.max(ResourceLearningEventModel.sequence_number)).where(
                        ResourceLearningEventModel.session_id == session_id
                    )
                )
                if sequence_number != int(last_sequence or 0) + 1:
                    raise ValueError("sequence number must be contiguous")

                occurred_at = _timestamp(event["occurred_at"])
                record = ResourceLearningEventModel(
                    event_id=event_id,
                    session_id=session_id,
                    sequence_number=sequence_number,
                    event_type=str(event["event_type"]),
                    scene_id=str(event["scene_id"]),
                    timeline_from_ms=event.get("timeline_from_ms"),
                    timeline_to_ms=event.get("timeline_to_ms"),
                    action_id=(str(event["action_id"]) if event.get("action_id") else None),
                    occurred_at=occurred_at,
                    received_at=now,
                    validation_status="accepted",
                )
                session.add(record)
                session.flush()
                created_any = True
                if record.event_type == "timeline_heartbeat":
                    self._merge_coverage(session, learning_session, record, now)
                learning_session.last_heartbeat_at = now

            progress = self._ensure_progress(
                session,
                course_id=learning_session.course_id,
                resource_id=learning_session.resource_id,
                resource_version=learning_session.resource_version,
                student_id=student_id,
                now=now,
            )
            if created_any:
                self._recalculate_progress(session, progress, now=now)
            session.flush()
            return self._progress(progress)

    def submit_questions(
        self,
        *,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
        answers: Mapping[str, object],
        idempotency_key: str,
        now: datetime,
    ) -> ResourceLearningProgressRecord:
        with database_session(engine=self._engine) as session:
            manifest_model = self._manifest_query(
                session, course_id, resource_id, resource_version
            )
            if manifest_model is None:
                raise KeyError((course_id, resource_id, resource_version))
            manifest = self._manifest(manifest_model)
            already_recorded = session.scalar(
                select(ResourceQuestionAttemptModel.question_attempt_id).where(
                    ResourceQuestionAttemptModel.student_id == student_id,
                    ResourceQuestionAttemptModel.course_id == course_id,
                    ResourceQuestionAttemptModel.resource_id == resource_id,
                    ResourceQuestionAttemptModel.resource_version == resource_version,
                    ResourceQuestionAttemptModel.idempotency_key == idempotency_key,
                )
            )
            progress = self._ensure_progress(
                session,
                course_id=course_id,
                resource_id=resource_id,
                resource_version=resource_version,
                student_id=student_id,
                now=now,
            )
            if already_recorded is not None:
                return self._progress(progress)

            questions = {item.question_id: item for item in manifest.questions}
            for question_id, answer in answers.items():
                question = questions[question_id]
                latest_number = session.scalar(
                    select(func.max(ResourceQuestionAttemptModel.attempt_number)).where(
                        ResourceQuestionAttemptModel.student_id == student_id,
                        ResourceQuestionAttemptModel.course_id == course_id,
                        ResourceQuestionAttemptModel.resource_id == resource_id,
                        ResourceQuestionAttemptModel.resource_version == resource_version,
                        ResourceQuestionAttemptModel.question_id == question_id,
                    )
                )
                submitted_values = _answer_values(answer)
                session.add(
                    ResourceQuestionAttemptModel(
                        question_attempt_id=f"rqa_{uuid4().hex}",
                        student_id=student_id,
                        course_id=course_id,
                        resource_id=resource_id,
                        resource_version=resource_version,
                        question_id=question_id,
                        attempt_number=int(latest_number or 0) + 1,
                        idempotency_key=idempotency_key,
                        answer_payload={"values": list(submitted_values)},
                        is_correct=submitted_values == tuple(sorted(question.scoring_values)),
                        knowledge_point_ids=list(question.knowledge_point_ids),
                        submitted_at=now,
                    )
                )
            session.flush()
            self._recalculate_progress(session, progress, now=now)
            session.flush()
            return self._progress(progress)

    def end_session(
        self, *, session_id: str, student_id: str, now: datetime
    ) -> ResourceLearningSessionRecord:
        with database_session(engine=self._engine) as session:
            record = session.get(ResourceLearningSessionModel, session_id)
            if record is None:
                raise KeyError(session_id)
            if record.student_id != student_id:
                raise PermissionError("session owner mismatch")
            if record.status == "active":
                record.status = "ended"
                record.ended_at = now
            session.flush()
            return self._session(record)

    def get_progress(
        self, course_id: str, resource_id: str, resource_version: int, student_id: str
    ) -> ResourceLearningProgressRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.get(
                ResourceLearningProgressModel,
                (student_id, course_id, resource_id, resource_version),
            )
            return self._progress(record) if record is not None else None

    def list_progress(
        self,
        *,
        course_id: str,
        resource_id: str | None = None,
        resource_version: int | None = None,
        student_id: str | None = None,
    ) -> list[tuple[str, ResourceLearningProgressRecord]]:
        with database_session(engine=self._engine) as session:
            statement = select(ResourceLearningProgressModel).where(
                ResourceLearningProgressModel.course_id == course_id
            )
            if resource_id is not None:
                statement = statement.where(
                    ResourceLearningProgressModel.resource_id == resource_id
                )
            if resource_version is not None:
                statement = statement.where(
                    ResourceLearningProgressModel.resource_version == resource_version
                )
            if student_id is not None:
                statement = statement.where(
                    ResourceLearningProgressModel.student_id == student_id
                )
            records = session.scalars(
                statement.order_by(
                    ResourceLearningProgressModel.student_id,
                    ResourceLearningProgressModel.resource_id,
                    ResourceLearningProgressModel.resource_version,
                )
            ).all()
            return [(item.student_id, self._progress(item)) for item in records]

    @staticmethod
    def _manifest_query(session, course_id: str, resource_id: str, resource_version: int):
        return session.scalar(
            select(ResourceLearningManifestModel).where(
                ResourceLearningManifestModel.course_id == course_id,
                ResourceLearningManifestModel.resource_id == resource_id,
                ResourceLearningManifestModel.resource_version == resource_version,
            )
        )

    @staticmethod
    def _ensure_progress(
        session,
        *,
        course_id: str,
        resource_id: str,
        resource_version: int,
        student_id: str,
        now: datetime,
    ):
        key = (student_id, course_id, resource_id, resource_version)
        record = session.get(ResourceLearningProgressModel, key)
        if record is not None:
            return record
        manifest = ResourceLearningRepository._manifest_query(
            session, course_id, resource_id, resource_version
        )
        if manifest is None:
            raise KeyError((course_id, resource_id, resource_version))
        domain = ResourceLearningRepository._manifest(manifest)
        record = ResourceLearningProgressModel(
            student_id=student_id,
            course_id=course_id,
            resource_id=resource_id,
            resource_version=resource_version,
            status="not_started",
            explanation_covered_ms=0,
            explanation_total_ms=domain.explanation_total_ms,
            explanation_coverage_percent=0,
            required_question_count=len(domain.required_question_ids),
            answered_question_count=0,
            question_completion_percent=0,
            correct_count_first=0,
            correct_count_latest=0,
            demo_view_count=0,
            demo_interaction_count=0,
            updated_at=now,
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def _merge_coverage(session, learning_session, event, now: datetime) -> None:
        key = (
            learning_session.student_id,
            learning_session.course_id,
            learning_session.resource_id,
            learning_session.resource_version,
            event.scene_id,
        )
        coverage = session.get(ResourceLearningCoverageModel, key)
        ranges = list(coverage.covered_ranges_json or []) if coverage is not None else []
        ranges.append([int(event.timeline_from_ms), int(event.timeline_to_ms)])
        manifest = ResourceLearningRepository._manifest_query(
            session,
            learning_session.course_id,
            learning_session.resource_id,
            learning_session.resource_version,
        )
        domain = ResourceLearningRepository._manifest(manifest)
        total_ms = next(item.expected_duration_ms for item in domain.scenes if item.scene_id == event.scene_id)
        merged = merge_covered_ranges(
            ((int(item[0]), int(item[1])) for item in ranges), total_ms=total_ms
        )
        if coverage is None:
            coverage = ResourceLearningCoverageModel(
                student_id=learning_session.student_id,
                course_id=learning_session.course_id,
                resource_id=learning_session.resource_id,
                resource_version=learning_session.resource_version,
                scene_id=event.scene_id,
            )
            session.add(coverage)
        coverage.covered_ranges_json = [list(item) for item in merged]
        coverage.covered_duration_ms = covered_duration_ms(merged)
        coverage.updated_at = now

    @staticmethod
    def _recalculate_progress(session, progress, *, now: datetime) -> None:
        manifest_model = ResourceLearningRepository._manifest_query(
            session, progress.course_id, progress.resource_id, progress.resource_version
        )
        manifest = ResourceLearningRepository._manifest(manifest_model)
        coverage_rows = session.scalars(
            select(ResourceLearningCoverageModel).where(
                ResourceLearningCoverageModel.student_id == progress.student_id,
                ResourceLearningCoverageModel.course_id == progress.course_id,
                ResourceLearningCoverageModel.resource_id == progress.resource_id,
                ResourceLearningCoverageModel.resource_version == progress.resource_version,
            )
        ).all()
        covered_ms = sum(item.covered_duration_ms for item in coverage_rows)
        attempts = session.scalars(
            select(ResourceQuestionAttemptModel)
            .where(
                ResourceQuestionAttemptModel.student_id == progress.student_id,
                ResourceQuestionAttemptModel.course_id == progress.course_id,
                ResourceQuestionAttemptModel.resource_id == progress.resource_id,
                ResourceQuestionAttemptModel.resource_version == progress.resource_version,
            )
            .order_by(
                ResourceQuestionAttemptModel.question_id,
                ResourceQuestionAttemptModel.attempt_number,
            )
        ).all()
        required_ids = set(manifest.required_question_ids)
        by_question: dict[str, list[Any]] = {}
        for attempt in attempts:
            if attempt.question_id in required_ids:
                by_question.setdefault(attempt.question_id, []).append(attempt)
        answered = len(by_question)
        required = len(required_ids)
        explanation_percent = coverage_percent(covered_ms, manifest.explanation_total_ms)
        question_percent = coverage_percent(answered, required)
        demo_views = session.scalar(
            select(func.count(ResourceLearningEventModel.event_id))
            .join(ResourceLearningSessionModel)
            .where(
                ResourceLearningSessionModel.student_id == progress.student_id,
                ResourceLearningSessionModel.course_id == progress.course_id,
                ResourceLearningSessionModel.resource_id == progress.resource_id,
                ResourceLearningSessionModel.resource_version == progress.resource_version,
                ResourceLearningEventModel.event_type == "demo_entered",
                ResourceLearningEventModel.validation_status == "accepted",
            )
        ) or 0
        demo_interactions = session.scalar(
            select(func.count(ResourceLearningEventModel.event_id))
            .join(ResourceLearningSessionModel)
            .where(
                ResourceLearningSessionModel.student_id == progress.student_id,
                ResourceLearningSessionModel.course_id == progress.course_id,
                ResourceLearningSessionModel.resource_id == progress.resource_id,
                ResourceLearningSessionModel.resource_version == progress.resource_version,
                ResourceLearningEventModel.event_type == "demo_interacted",
                ResourceLearningEventModel.validation_status == "accepted",
            )
        ) or 0
        has_activity = bool(covered_ms or attempts or demo_views or demo_interactions)
        completed = (
            manifest.mode == "completable"
            and explanation_percent >= 80.0
            and answered == required
        )
        if completed or progress.status == "completed":
            progress.status = "completed"
            progress.completed_at = progress.completed_at or now
        elif has_activity:
            progress.status = "in_progress"
        progress.explanation_covered_ms = covered_ms
        progress.explanation_total_ms = manifest.explanation_total_ms
        progress.explanation_coverage_percent = explanation_percent
        progress.required_question_count = required
        progress.answered_question_count = answered
        progress.question_completion_percent = question_percent
        progress.correct_count_first = sum(1 for values in by_question.values() if values[0].is_correct)
        progress.correct_count_latest = sum(1 for values in by_question.values() if values[-1].is_correct)
        progress.demo_view_count = int(demo_views)
        progress.demo_interaction_count = int(demo_interactions)
        if has_activity:
            progress.started_at = progress.started_at or now
            progress.last_activity_at = now
        progress.updated_at = now

    @staticmethod
    def _manifest(record: ResourceLearningManifestModel) -> ResourceLearningManifestRecord:
        payload = record.manifest_json or {}
        scenes = tuple(
            ManifestScene(
                scene_id=str(item["scene_id"]),
                kind=item["kind"],
                expected_duration_ms=int(item["expected_duration_ms"]),
                required_action_ids=tuple(item.get("required_action_ids") or ()),
                required_question_ids=tuple(item.get("required_question_ids") or ()),
            )
            for item in payload.get("scenes", [])
        )
        questions = tuple(
            ManifestQuestion(
                question_id=str(item["question_id"]),
                scene_id=str(item["scene_id"]),
                question_type=str(item["question_type"]),
                required=bool(item["required"]),
                scoring_values=tuple(item.get("scoring_values") or ()),
                knowledge_point_ids=tuple(item.get("knowledge_point_ids") or ()),
            )
            for item in payload.get("questions", [])
        )
        return ResourceLearningManifestRecord(
            manifest_id=record.manifest_id,
            course_id=record.course_id,
            resource_id=record.resource_id,
            resource_version=record.resource_version,
            content_hash=record.content_hash,
            mode=record.mode,
            scenes=scenes,
            questions=questions,
            created_at=_iso(record.created_at) or "",
        )

    @staticmethod
    def _session(record: ResourceLearningSessionModel) -> ResourceLearningSessionRecord:
        return ResourceLearningSessionRecord(
            session_id=record.session_id,
            course_id=record.course_id,
            resource_id=record.resource_id,
            resource_version=record.resource_version,
            status=record.status,
            started_at=_iso(record.started_at) or "",
            last_heartbeat_at=_iso(record.last_heartbeat_at),
            ended_at=_iso(record.ended_at),
        )

    @staticmethod
    def _progress(record: ResourceLearningProgressModel) -> ResourceLearningProgressRecord:
        return ResourceLearningProgressRecord(
            course_id=record.course_id,
            resource_id=record.resource_id,
            resource_version=record.resource_version,
            status=record.status,
            explanation_covered_ms=record.explanation_covered_ms,
            explanation_total_ms=record.explanation_total_ms,
            explanation_coverage_percent=record.explanation_coverage_percent,
            required_question_count=record.required_question_count,
            answered_question_count=record.answered_question_count,
            question_completion_percent=record.question_completion_percent,
            correct_count_first=record.correct_count_first,
            correct_count_latest=record.correct_count_latest,
            demo_view_count=record.demo_view_count,
            demo_interaction_count=record.demo_interaction_count,
            started_at=_iso(record.started_at),
            completed_at=_iso(record.completed_at),
            last_activity_at=_iso(record.last_activity_at),
            updated_at=_iso(record.updated_at) or "",
        )
