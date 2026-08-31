from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.database.models import TaskResourceEvidenceRefModel
from app.database.session import database_session
from app.learning.models import LearningTaskRecord, TaskResourceEvidence

from .models import ResourceLearningProgressRecord
from .repository import ResourceLearningRepository


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


class TaskResourceEvidenceAdapter:
    def __init__(self, repository: ResourceLearningRepository):
        self.repository = repository

    @staticmethod
    def _classroom_refs(task: LearningTaskRecord) -> list[tuple[str, int]]:
        return [
            (snapshot.source_material_id, snapshot.source_version)
            for snapshot in task.resource_snapshots
            if snapshot.source_material_type == "classroom"
            and snapshot.origin_type == "standard"
        ]

    def initialize_task(
        self, task: LearningTaskRecord, *, student_ids: Sequence[str]
    ) -> list[TaskResourceEvidence]:
        for student_id in student_ids:
            self.ensure_for_student(task, student_id=student_id)
        return self.list_for_task_student(
            task.task_id, student_id=student_ids[0]
        ) if student_ids else []

    def ensure_for_student(
        self, task: LearningTaskRecord, *, student_id: str
    ) -> list[TaskResourceEvidence]:
        refs = self._classroom_refs(task)
        if not refs:
            return []
        with database_session(engine=self.repository._engine) as session:
            for resource_id, resource_version in refs:
                existing = session.scalar(
                    select(TaskResourceEvidenceRefModel).where(
                        TaskResourceEvidenceRefModel.task_id == task.task_id,
                        TaskResourceEvidenceRefModel.student_id == student_id,
                        TaskResourceEvidenceRefModel.resource_id == resource_id,
                        TaskResourceEvidenceRefModel.resource_version == resource_version,
                    )
                )
                if existing is not None:
                    continue
                progress = self.repository.get_progress(
                    task.course_id, resource_id, resource_version, student_id
                )
                satisfied = progress is not None and progress.status == "completed"
                session.add(
                    TaskResourceEvidenceRefModel(
                        evidence_ref_id=f"tre_{uuid4().hex}",
                        task_id=task.task_id,
                        student_id=student_id,
                        resource_id=resource_id,
                        resource_version=resource_version,
                        resource_progress_updated_at=(
                            _timestamp(progress.updated_at) if progress else None
                        ),
                        resource_completed_at=(
                            _timestamp(progress.completed_at) if satisfied else None
                        ),
                        condition_status="satisfied" if satisfied else "pending",
                        linked_at=datetime.now(UTC),
                    )
                )
        return self.list_for_task_student(task.task_id, student_id=student_id)

    def satisfy_for_progress(
        self, *, student_id: str, progress: ResourceLearningProgressRecord
    ) -> int:
        if progress.status != "completed":
            return 0
        with database_session(engine=self.repository._engine) as session:
            records = session.scalars(
                select(TaskResourceEvidenceRefModel).where(
                    TaskResourceEvidenceRefModel.student_id == student_id,
                    TaskResourceEvidenceRefModel.resource_id == progress.resource_id,
                    TaskResourceEvidenceRefModel.resource_version == progress.resource_version,
                    TaskResourceEvidenceRefModel.condition_status == "pending",
                )
            ).all()
            for record in records:
                record.condition_status = "satisfied"
                record.resource_progress_updated_at = _timestamp(progress.updated_at)
                record.resource_completed_at = _timestamp(progress.completed_at)
            return len(records)

    def list_for_task_student(
        self, task_id: str, *, student_id: str
    ) -> list[TaskResourceEvidence]:
        with database_session(engine=self.repository._engine) as session:
            records = session.scalars(
                select(TaskResourceEvidenceRefModel)
                .where(
                    TaskResourceEvidenceRefModel.task_id == task_id,
                    TaskResourceEvidenceRefModel.student_id == student_id,
                )
                .order_by(
                    TaskResourceEvidenceRefModel.resource_id,
                    TaskResourceEvidenceRefModel.resource_version,
                )
            ).all()
            return [
                TaskResourceEvidence(
                    resource_id=item.resource_id,
                    resource_version=item.resource_version,
                    condition_status=item.condition_status,
                    resource_completed_at=_iso(item.resource_completed_at),
                )
                for item in records
            ]
