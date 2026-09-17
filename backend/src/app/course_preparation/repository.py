"""Transactional intake. PostgreSQL constraints arbitrate concurrent submissions.

No public API is registered in this phase. Callers must supply an authenticated
database user ID and a concrete authorizer; there is no permissive default.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import CoursePreparationRecord, CoursePreparationAttemptRecord, CoursePreparationEventRecord
from .contracts import (IdempotencyConflict, PreparationAuthorizer, PreparationEvent,
                        PreparationNotFound, PreparationSnapshot)
from .schemas import PreparationRequest, request_digest


def aware(value: datetime) -> datetime:
    # SQLite test storage drops timezone information; PostgreSQL preserves it.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class PreparationRepository:
    def __init__(self, engine: Engine, *, authorizer: PreparationAuthorizer):
        self.engine = engine
        self.authorizer = authorizer

    @staticmethod
    def _request_record(session, owner_user_id, request_id):
        return session.scalar(select(CoursePreparationRecord).where(
            CoursePreparationRecord.owner_user_id == owner_user_id,
            CoursePreparationRecord.request_id == str(request_id),
        ))

    @staticmethod
    def _owned_record(session, owner_user_id, preparation_id):
        record = session.scalar(select(CoursePreparationRecord).where(
            CoursePreparationRecord.owner_user_id == owner_user_id,
            CoursePreparationRecord.preparation_id == preparation_id,
        ))
        if record is None:
            raise PreparationNotFound('preparation not found')
        return record

    @staticmethod
    def _snapshot(session: Session, record: CoursePreparationRecord) -> PreparationSnapshot:
        attempt = session.get(CoursePreparationAttemptRecord, (record.preparation_id, record.current_attempt_no))
        if attempt is None:
            raise RuntimeError('preparation has no current attempt')
        return PreparationSnapshot(
            preparation_id=record.preparation_id, status=attempt.status, stage=attempt.stage,
            attempt_no=attempt.attempt_no, revision=record.revision, created_at=aware(record.created_at),
            request=PreparationRequest.model_validate(record.request_payload),
        )

    def _replay(self, session, record, digest):
        if record.request_sha256 != digest:
            raise IdempotencyConflict('request_id is already bound to a different preparation request')
        return self._snapshot(session, record)

    def accept(self, *, owner_user_id: str, request: PreparationRequest, initialize=None) -> PreparationSnapshot:
        request = PreparationRequest.model_validate(request.model_dump(mode='json'))
        self.authorizer.authorize(owner_user_id, request)
        digest = request_digest(request)
        try:
            with Session(self.engine) as session, session.begin():
                existing = self._request_record(session, owner_user_id, request.request_id)
                if existing is not None:
                    return self._replay(session, existing, digest)
                now = datetime.now(timezone.utc)
                record = CoursePreparationRecord(
                    preparation_id='prep_' + uuid4().hex, owner_user_id=owner_user_id,
                    request_id=str(request.request_id), request_sha256=digest, operation=request.operation,
                    request_payload=request.model_dump(mode='json'), current_attempt_no=1, revision=1,
                    created_at=now,
                )
                session.add(record)
                session.flush()  # Owner/request unique constraint serializes racing accepts.
                session.add(CoursePreparationAttemptRecord(
                    preparation_id=record.preparation_id, attempt_no=1,
                    status='accepted', stage='normalize', created_at=now,
                ))
                session.flush()
                session.add(CoursePreparationEventRecord(
                    event_id='pevt_' + uuid4().hex, preparation_id=record.preparation_id,
                    attempt_no=1, sequence=1, event_type='accepted', revision=1,
                    payload={'operation': request.operation}, occurred_at=now,
                ))
                session.flush()
                if initialize is not None:
                    initialize(session, record)
                    session.flush()
                result = self._snapshot(session, record)
            return result
        except IntegrityError as exc:
            # Only a committed matching intake is a replay. Other integrity
            # failures (owner FK, malformed event, etc.) remain real errors.
            constraint = getattr(getattr(exc.orig, 'diag', None), 'constraint_name', None)
            is_request_conflict = constraint == 'uq_course_preparation_request'
            if self.engine.dialect.name == 'sqlite':
                is_request_conflict = str(exc.orig) == (
                    'UNIQUE constraint failed: course_preparations.owner_user_id, course_preparations.request_id'
                )
            if not is_request_conflict:
                raise
            with Session(self.engine) as session:
                existing = self._request_record(session, owner_user_id, request.request_id)
                if existing is None:
                    raise
                self.authorizer.authorize(owner_user_id, request)
                return self._replay(session, existing, digest)

    def get(self, *, owner_user_id: str, preparation_id: str) -> PreparationSnapshot:
        with Session(self.engine) as session:
            record = self._owned_record(session, owner_user_id, preparation_id)
            snapshot = self._snapshot(session, record)
            self.authorizer.authorize(owner_user_id, snapshot.request)
            return snapshot

    def events(self, *, owner_user_id: str, preparation_id: str,
               after: int = 0, limit: int = 100) -> list[PreparationEvent]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('after must be nonnegative and limit must be between 1 and 500')
        with Session(self.engine) as session:
            record = self._owned_record(session, owner_user_id, preparation_id)
            request = PreparationRequest.model_validate(record.request_payload)
            self.authorizer.authorize(owner_user_id, request)
            rows = session.scalars(select(CoursePreparationEventRecord).where(
                CoursePreparationEventRecord.preparation_id == preparation_id,
                CoursePreparationEventRecord.sequence > after,
            ).order_by(CoursePreparationEventRecord.sequence).limit(limit)).all()
            return [PreparationEvent(
                event_id=row.event_id, preparation_id=row.preparation_id, attempt_no=row.attempt_no,
                sequence=row.sequence, type=row.event_type, revision=row.revision,
                occurred_at=aware(row.occurred_at), origin_ref=request.origin, payload=row.payload,
            ) for row in rows]
