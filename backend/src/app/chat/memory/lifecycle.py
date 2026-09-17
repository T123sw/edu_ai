"""Shared preference watermarks, source suppression and derivation validity.

Lock order: memory epoch, preparation, course pointer. User changes never lock
preparations: consumers check dependencies synchronously before accepting output.
"""
from datetime import datetime, timezone
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import (MemoryEpoch, MemorySuppression, MemoryDependency,
                                 MemoryChangeEvent, AgentMemoryItem)


class MemoryChanged(ValueError): pass
class MemorySuppressed(MemoryChanged): pass


def source_digest(source_id):
    return hashlib.sha256(source_id.encode()).hexdigest()


def lock_epoch(session, subject):
    dialect = session.bind.dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError('Unsupported memory database')
    session.execute(insert(MemoryEpoch).values(subject_user_id=subject, epoch=0)
                    .on_conflict_do_nothing(index_elements=['subject_user_id']))
    return session.scalar(select(MemoryEpoch).where(MemoryEpoch.subject_user_id == subject).with_for_update())


def suppress(session, subject, source_id, epoch):
    key = (subject, source_digest(source_id))
    if session.get(MemorySuppression, key) is None:
        session.add(MemorySuppression(subject_user_id=subject, source_digest=key[1], source_id=source_id, epoch=epoch))


def changed(session, watermark, affected):
    watermark.epoch += 1
    ids = set(affected)
    for dependency in session.scalars(select(MemoryDependency).where(
            MemoryDependency.subject_user_id == watermark.subject_user_id, MemoryDependency.valid.is_(True))):
        if ids.intersection(dependency.source_refs):
            dependency.valid = False
    session.add(MemoryChangeEvent(subject_user_id=watermark.subject_user_id, epoch=watermark.epoch,
                                 affected_memory_ids=sorted(ids), delivered=False))
    session.flush()


def revision(record):
    # Existing memories have no numeric revision. Bind content/status/source hash.
    value = [record.memory_id, record.content, record.status, record.source_id,
             record.source_span, record.course_id, record.profile_axis]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def expired(record):
    now = datetime.now(timezone.utc)
    start = record.valid_from
    end = record.valid_until
    return ((start is not None and start.replace(tzinfo=start.tzinfo or timezone.utc) > now)
            or (end is not None and end.replace(tzinfo=end.tzinfo or timezone.utc) <= now))


class MemoryLifecycle:
    def __init__(self, engine): self.engine = engine

    def current_epoch(self, subject):
        with Session(self.engine) as session, session.begin():
            return lock_epoch(session, subject).epoch

    def read_effective(self, subject, *, course_id=None, fields=None, expected_epoch=None):
        with Session(self.engine) as session, session.begin():
            epoch = lock_epoch(session, subject).epoch
            if expected_epoch is not None and epoch != expected_epoch: raise MemoryChanged('MEMORY_EPOCH_CHANGED')
            records = session.scalars(select(AgentMemoryItem).where(
                AgentMemoryItem.subject_user_id == subject, AgentMemoryItem.status == 'active',
                AgentMemoryItem.profile_axis.is_not(None))).all()
            values = {}
            for record in sorted(records, key=lambda r: (r.course_id is not None, r.updated_at, r.memory_id)):
                if record.course_id not in (None, course_id) or expired(record): continue
                if fields is not None and record.profile_axis not in fields: continue
                # Preparation reads explicit preferences; inferred memories stay out.
                if record.fact_kind not in ('fact', 'preference'): continue
                if session.get(MemorySuppression, (subject, source_digest(record.source_id))): continue
                values[record.profile_axis] = {'memory_id': record.memory_id, 'revision': revision(record),
                    'value': record.content, 'course_id': record.course_id}
            return {'memory_epoch': epoch, 'preferences': dict(list(values.items())[:8])}

    def register_dependencies(self, subject, consumer_ref, source_refs, *, expected_epoch):
        with Session(self.engine) as session, session.begin():
            epoch = lock_epoch(session, subject).epoch
            if epoch != expected_epoch: raise MemoryChanged('MEMORY_EPOCH_CHANGED')
            self.validate_refs_in_session(session, subject, source_refs)
            record = session.get(MemoryDependency, (subject, consumer_ref))
            if record is None:
                record = MemoryDependency(subject_user_id=subject, consumer_ref=consumer_ref)
                session.add(record)
            record.epoch, record.source_refs, record.valid = epoch, dict(source_refs), True
            return {'consumer_ref': consumer_ref, 'memory_epoch': epoch}

    @staticmethod
    def validate_refs_in_session(session, subject, refs):
        for memory_id, expected in refs.items():
            record = session.get(AgentMemoryItem, memory_id)
            if (record is None or record.subject_user_id != subject or record.status != 'active'
                    or expired(record) or revision(record) != expected
                    or session.get(MemorySuppression, (subject, source_digest(record.source_id)))):
                raise MemoryChanged('MEMORY_DEPENDENCY_INVALID')

    def validate_consumer(self, subject, consumer_ref):
        with Session(self.engine) as session, session.begin():
            epoch = lock_epoch(session, subject).epoch
            record = session.get(MemoryDependency, (subject, consumer_ref))
            if record is None or not record.valid: raise MemoryChanged('MEMORY_DEPENDENCY_INVALID')
            self.validate_refs_in_session(session, subject, record.source_refs)
            record.epoch = epoch
            return epoch

    def source_is_suppressed(self, subject, source_id):
        with Session(self.engine) as session:
            return session.get(MemorySuppression, (subject, source_digest(source_id))) is not None
