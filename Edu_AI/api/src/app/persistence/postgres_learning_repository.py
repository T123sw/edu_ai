from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import (
    LearningEventModel,
    LearningProgressModel,
    LearningTaskModel,
    database_session,
)
from app.learning.models import (
    EventWriteResult,
    LearningEventRecord,
    LearningTaskRecord,
    TaskProgressRecord,
    utc_now,
)
from app.learning.store import _event_basis, _max_basis

from .postgres_repositories import _iso_timestamp, _timestamp


class PostgresLearningRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create_task(self, task: LearningTaskRecord) -> LearningTaskRecord:
        with database_session(engine=self._engine) as session:
            session.add(LearningTaskModel(
                task_id=task.task_id, course_id=task.course_id, title=task.title,
                instructions=task.instructions, created_by=task.created_by,
                resource_refs=task.resource_refs, knowledge_point_ids=task.knowledge_point_ids,
                status=task.status, created_at=_timestamp(task.created_at),
                published_at=_timestamp(task.published_at) if task.published_at else None,
                published_by=task.published_by,
            ))
        return task

    def get_task(self, task_id: str, course_id: str) -> LearningTaskRecord | None:
        with database_session(engine=self._engine) as session:
            record = session.get(LearningTaskModel, task_id)
            if record is None or record.course_id != course_id:
                return None
            return self._task(record)

    def list_tasks(self, course_id: str, statuses=None, limit=None):
        with database_session(engine=self._engine) as session:
            statement = select(LearningTaskModel).where(LearningTaskModel.course_id == course_id)
            if statuses:
                statement = statement.where(LearningTaskModel.status.in_(list(statuses)))
            statement = statement.order_by(LearningTaskModel.created_at.desc(), LearningTaskModel.task_id.desc())
            if limit is not None:
                statement = statement.limit(max(0, int(limit)))
            return [self._task(item) for item in session.scalars(statement).all()]

    def publish_task(self, task_id: str, course_id: str, published_by: str):
        with database_session(engine=self._engine) as session:
            record = session.get(LearningTaskModel, task_id)
            if record is None or record.course_id != course_id or record.status not in {"draft", "published"}:
                raise KeyError(task_id)
            record.status = "published"
            record.published_at = record.published_at or _timestamp(utc_now())
            record.published_by = record.published_by or published_by
            session.flush()
            return self._task(record)

    def update_task_knowledge_points(
        self, task_id: str, course_id: str, knowledge_point_ids: list[str]
    ) -> LearningTaskRecord:
        with database_session(engine=self._engine) as session:
            record = session.get(LearningTaskModel, task_id)
            if (
                record is None
                or record.course_id != course_id
                or record.status != "draft"
            ):
                raise KeyError(task_id)
            record.knowledge_point_ids = list(knowledge_point_ids)
            session.flush()
            return self._task(record)

    def record_event(self, event: LearningEventRecord) -> EventWriteResult:
        if not 0 <= event.progress_percent <= 100:
            raise ValueError("progress_percent must be between 0 and 100")
        with database_session(engine=self._engine) as session:
            task = session.get(LearningTaskModel, event.task_id)
            if task is None or task.course_id != event.course_id:
                raise KeyError(event.task_id)
            insert = self._insert_for(session)
            event_insert = self._event_insert(insert, event)
            created = session.execute(event_insert).scalar_one_or_none() is not None
            if created:
                session.execute(
                    insert(LearningProgressModel).values(
                        task_id=event.task_id,
                        student_id=event.student_id,
                        course_id=event.course_id,
                        status="not_started",
                        progress_percent=0,
                        completion_basis="none",
                        evidence_count=0,
                        last_activity_at=None,
                        started_at=None,
                        completed_at=None,
                        updated_at=_timestamp(event.occurred_at),
                    ).on_conflict_do_nothing(
                        index_elements=[
                            LearningProgressModel.task_id,
                            LearningProgressModel.student_id,
                        ]
                    )
                )
                progress = session.scalar(
                    select(LearningProgressModel).where(
                        LearningProgressModel.task_id == event.task_id,
                        LearningProgressModel.student_id == event.student_id,
                    ).with_for_update()
                )
                if progress is None:
                    raise RuntimeError("learning event exists without task progress")
                completed = progress.status == "completed" or event.event_type == "completed"
                progress.progress_percent = (
                    100 if completed else max(progress.progress_percent, event.progress_percent)
                )
                if completed:
                    progress.status = "completed"
                elif event.event_type in {
                    "started",
                    "resource_opened",
                    "progress_updated",
                    "resource_completed",
                    "assessment_scored",
                }:
                    progress.status = "in_progress"
                progress.started_at = progress.started_at or _timestamp(event.occurred_at)
                if completed:
                    progress.completed_at = progress.completed_at or _timestamp(event.occurred_at)
                progress.completion_basis = _max_basis(
                    str(progress.completion_basis or "none"),
                    _event_basis(event.event_type),
                )
                progress.evidence_count = int(progress.evidence_count or 0) + 1
                progress.last_activity_at = _timestamp(event.occurred_at)
                progress.updated_at = _timestamp(event.occurred_at)
            progress = session.get(LearningProgressModel, (event.task_id, event.student_id))
            if progress is None:
                raise RuntimeError("learning event exists without task progress")
            session.flush()
            return EventWriteResult(created=created, progress=self._progress(progress))

    @classmethod
    def _event_insert(cls, insert, event: LearningEventRecord):
        return insert(LearningEventModel).values(
                event_id=event.event_id,
                course_id=event.course_id,
                task_id=event.task_id,
                student_id=event.student_id,
                event_type=event.event_type,
                progress_percent=event.progress_percent,
                resource_ref=event.resource_ref,
                evidence=cls._evidence(event),
                occurred_at=_timestamp(event.occurred_at),
            ).on_conflict_do_nothing(
                index_elements=[LearningEventModel.event_id]
            ).returning(LearningEventModel.event_id)

    @staticmethod
    def _insert_for(session):
        dialect_name = session.bind.dialect.name
        if dialect_name == "postgresql":
            return postgresql_insert
        if dialect_name == "sqlite":
            return sqlite_insert
        raise RuntimeError(f"Unsupported learning persistence dialect: {dialect_name}")

    @staticmethod
    def _evidence(event: LearningEventRecord) -> dict | None:
        if event.evidence is None:
            return None
        return {
            "evidence_type": event.evidence.evidence_type,
            "source_type": event.evidence.source_type,
            "source_id": event.evidence.source_id,
            "value": event.evidence.value,
            "occurred_at": event.evidence.occurred_at,
        }

    def get_progress(self, task_id: str, student_id: str):
        with database_session(engine=self._engine) as session:
            record = session.get(LearningProgressModel, (task_id, student_id))
            return self._progress(record) if record else None

    def list_progress(self, course_id: str, task_id: str):
        with database_session(engine=self._engine) as session:
            records = session.scalars(select(LearningProgressModel).where(
                LearningProgressModel.course_id == course_id,
                LearningProgressModel.task_id == task_id,
            ).order_by(LearningProgressModel.student_id)).all()
            return [self._progress(item) for item in records]

    @staticmethod
    def _task(record: LearningTaskModel) -> LearningTaskRecord:
        return LearningTaskRecord(
            task_id=record.task_id, course_id=record.course_id, title=record.title,
            instructions=record.instructions, created_by=record.created_by,
            resource_refs=list(record.resource_refs or []),
            knowledge_point_ids=list(record.knowledge_point_ids or []), status=record.status,
            created_at=_iso_timestamp(record.created_at),
            published_at=_iso_timestamp(record.published_at) if record.published_at else None,
            published_by=record.published_by,
        )

    @staticmethod
    def _progress(record: LearningProgressModel) -> TaskProgressRecord:
        return TaskProgressRecord(
            task_id=record.task_id, course_id=record.course_id, student_id=record.student_id,
            status=record.status, progress_percent=record.progress_percent,
            completion_basis=record.completion_basis,
            evidence_count=record.evidence_count,
            last_activity_at=(
                _iso_timestamp(record.last_activity_at) if record.last_activity_at else None
            ),
            started_at=_iso_timestamp(record.started_at) if record.started_at else None,
            completed_at=_iso_timestamp(record.completed_at) if record.completed_at else None,
            updated_at=_iso_timestamp(record.updated_at),
        )
