from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.database import JobEvent, JobRecord, database_session

from .postgres_repositories import _iso_timestamp, _required_text, _timestamp


def _optional_timestamp(value: object):
    return _timestamp(value) if str(value or "").strip() else None


class PostgresJobRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def upsert(self, job: Mapping[str, Any]) -> None:
        payload = dict(job)
        job_id = _required_text(payload.get("edu_job_id"), "edu_job_id")
        version = int(payload.get("version") or 1)
        status = _required_text(payload.get("status"), "status")
        step = str(payload.get("step") or status)
        updated_at = _timestamp(payload.get("updated_at"))
        with database_session(engine=self._engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                record = JobRecord(edu_job_id=job_id)
                session.add(record)
            record.kind = _required_text(payload.get("kind"), "kind")
            record.status = status
            record.step = step
            record.progress = int(payload.get("progress") or 0)
            record.version = version
            record.owner_user_id = str(
                payload.get("owner_user_id") or payload.get("owner") or ""
            ).strip()
            record.course_id = str(payload.get("course_id") or "").strip() or None
            record.scope_type = str(payload.get("scope_type") or "course")
            record.scope_id = str(payload.get("scope_id") or "").strip() or None
            record.retry_of_job_id = (
                str(payload.get("retry_of_job_id") or "").strip() or None
            )
            record.parent_job_id = (
                str(payload.get("parent_job_id") or "").strip() or None
            )
            record.created_at = _timestamp(payload.get("created_at"))
            record.started_at = _optional_timestamp(payload.get("started_at"))
            record.finished_at = _optional_timestamp(payload.get("finished_at"))
            record.updated_at = updated_at
            record.raw_payload = payload

            existing_event = session.scalar(
                select(JobEvent).where(
                    JobEvent.edu_job_id == job_id,
                    JobEvent.version == version,
                )
            )
            if existing_event is None:
                session.add(
                    JobEvent(
                        edu_job_id=job_id,
                        version=version,
                        status=status,
                        step=step,
                        occurred_at=updated_at,
                        payload=payload,
                    )
                )

    def get(self, edu_job_id: str) -> dict[str, Any] | None:
        job_id = _required_text(edu_job_id, "edu_job_id")
        with database_session(engine=self._engine) as session:
            record = session.get(JobRecord, job_id)
            return self._payload(record) if record is not None else None

    def list(self) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(JobRecord).order_by(
                    JobRecord.updated_at.desc(), JobRecord.edu_job_id.desc()
                )
            ).all()
            return [self._payload(record) for record in records]

    @staticmethod
    def _payload(record: JobRecord) -> dict[str, Any]:
        payload = dict(record.raw_payload or {})
        payload.update(
            {
                "edu_job_id": record.edu_job_id,
                "kind": record.kind,
                "status": record.status,
                "step": record.step,
                "progress": record.progress,
                "version": record.version,
                "owner_user_id": record.owner_user_id,
                "owner": record.owner_user_id or None,
                "course_id": record.course_id,
                "scope_type": record.scope_type,
                "scope_id": record.scope_id,
                "retry_of_job_id": record.retry_of_job_id,
                "parent_job_id": record.parent_job_id,
                "created_at": _iso_timestamp(record.created_at),
                "started_at": (
                    _iso_timestamp(record.started_at) if record.started_at else None
                ),
                "finished_at": (
                    _iso_timestamp(record.finished_at) if record.finished_at else None
                ),
                "updated_at": _iso_timestamp(record.updated_at),
            }
        )
        return payload
