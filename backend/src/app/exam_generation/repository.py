"""Private generation checkpoints in the existing application-state table."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from app.database.models import AppStateRecord
from app.database.session import database_session
from .progress import question_progress

NAMESPACE = 'exam_generation_v1'


class GenerationNotFound(LookupError): pass
class GenerationConflict(ValueError): pass


def identifier(owner, request_id):
    return 'examgen_' + hashlib.sha256(f'{owner}:{request_id}'.encode()).hexdigest()[:32]


class GenerationRepository:
    def __init__(self, engine=None):
        self.engine = engine

    def _row(self, session, owner, generation_id, *, lock=False):
        query = select(AppStateRecord).where(AppStateRecord.namespace == NAMESPACE,
            AppStateRecord.record_key == generation_id, AppStateRecord.owner_user_id == owner)
        row = session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise GenerationNotFound('生成记录不存在或无权访问')
        return row

    def get(self, owner, generation_id, *, include_events=True):
        with database_session(engine=self.engine) as session:
            cursor_record = aliased(AppStateRecord)
            cursor_query = select(cursor_record.payload).where(
                cursor_record.namespace == NAMESPACE + '_cursor',
                cursor_record.owner_user_id == owner, cursor_record.record_key == generation_id)
            # One statement sees result and cursor from the same DB snapshot;
            # reading them separately could skip a concurrently committed RESULT.
            snapshot = session.execute(select(AppStateRecord.payload, cursor_query.scalar_subquery()).where(
                AppStateRecord.namespace == NAMESPACE, AppStateRecord.owner_user_id == owner,
                AppStateRecord.record_key == generation_id)).first()
            if snapshot is None:
                raise GenerationNotFound('生成记录不存在或无权访问')
            value, cursor = deepcopy(snapshot[0]), snapshot[1]
            if cursor:
                value['last_seq'] = max(value['last_seq'], cursor['last_seq'])
            if not include_events:
                return value
            rows = session.scalars(select(AppStateRecord).where(
                AppStateRecord.namespace == NAMESPACE + '_events',
                AppStateRecord.owner_user_id == owner,
                AppStateRecord.record_key.like(generation_id + ':%')).order_by(AppStateRecord.record_key))
            value['events'] = [deepcopy(row.payload) for row in rows]
            return value

    def list(self, owner, limit=50):
        with database_session(engine=self.engine) as session:
            rows = session.execute(select(AppStateRecord.record_key,
                AppStateRecord.payload['job_id'].as_string(),
                AppStateRecord.payload['request'],
                AppStateRecord.payload['sources']).where(
                AppStateRecord.namespace == NAMESPACE,
                AppStateRecord.owner_user_id == owner).order_by(AppStateRecord.created_at.desc()).limit(limit))
            return [{'id': gid, 'job_id': job_id or gid, 'request': request, 'sources': sources or []}
                    for gid, job_id, request, sources in rows]

    def create(self, owner, request, *, sources, encrypted_snapshot):
        gid = identifier(owner, request['request_id'])
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        value = {'id': gid, 'job_id': gid, 'owner': owner, 'request': request, 'fingerprint': fingerprint,
                 'sources': sources, 'encrypted_snapshot': encrypted_snapshot, 'attempt': 0,
                 'session_id': None, 'turn_id': None, 'last_seq': 0, 'events': [],
                 'parsed_sources': None, 'result': None, 'remote_parse_tasks': []}
        try:
            with database_session(engine=self.engine) as session:
                session.add(AppStateRecord(namespace=NAMESPACE, record_key=gid, owner_user_id=owner, payload=value))
                session.flush()
        except IntegrityError:
            pass
        row = self.get(owner, gid, include_events=False)
        if row['fingerprint'] != fingerprint:
            raise GenerationConflict('此请求编号已用于其他生成要求')
        return row

    @contextmanager
    def lock(self, owner, gid):
        with database_session(engine=self.engine) as session:
            row = self._row(session, owner, gid, lock=True)
            value = deepcopy(row.payload)
            yield value
            row.payload = value

    def claim(self, owner, gid, attempt):
        with self.lock(owner, gid) as value:
            if attempt < value['attempt']:
                raise GenerationConflict('生成租约已过期')
            value['attempt'] = attempt
        return self.get(owner, gid, include_events=False)

    def update(self, owner, gid, attempt, changes):
        with self.lock(owner, gid) as value:
            if attempt != value['attempt']:
                raise GenerationConflict('生成租约已过期')
            value.update(deepcopy(changes))

    def event(self, owner, gid, attempt, event):
        self.events_batch(owner, gid, attempt, [event])

    def events_batch(self, owner, gid, attempt, events):
        with database_session(engine=self.engine) as session:
            # Lock the generation without transferring its PDF/image payload.
            state = session.execute(select(AppStateRecord.payload['attempt'].as_integer(),
                AppStateRecord.payload['last_seq'].as_integer()).where(
                AppStateRecord.namespace == NAMESPACE, AppStateRecord.record_key == gid,
                AppStateRecord.owner_user_id == owner).with_for_update()).first()
            if state is None:
                raise GenerationNotFound('生成记录不存在或无权访问')
            if attempt != state[0]:
                raise GenerationConflict('生成租约已过期')
            cursor = session.scalar(select(AppStateRecord).where(
                AppStateRecord.namespace == NAMESPACE + '_cursor',
                AppStateRecord.record_key == gid, AppStateRecord.owner_user_id == owner))
            last_seq = max(state[1], cursor.payload['last_seq'] if cursor else 0)
            value = None
            inserts = []
            for event in events:
                seq = int(event.get('seq', 0))
                if seq <= last_seq:
                    continue
                inserts.append(dict(namespace=NAMESPACE + '_events',
                    record_key=f'{gid}:{seq:020d}', owner_user_id=owner, payload=event))
                last_seq = seq
                blueprint = (event.get('metadata') or {}).get('exam_blueprint')
                progress = question_progress(event)
                if (blueprint is not None or event.get('type') == 'result' or progress is not None) and value is None:
                    row = self._row(session, owner, gid)
                    value = deepcopy(row.payload)
                if blueprint is not None:
                    if value.get('blueprint') is not None and value['blueprint'] != blueprint:
                        raise GenerationConflict('试卷蓝图不能在生成中改变')
                    value['blueprint'] = deepcopy(blueprint)
                if event.get('type') == 'result':
                    value['result'] = event
                if progress is not None:
                    previous = value.get('question_progress')
                    if previous is None or (progress['total'] == previous['total'] and
                                            progress['processed'] > previous['processed']):
                        value['question_progress'] = progress
            if inserts:
                session.execute(AppStateRecord.__table__.insert(), inserts)
            if value is not None:
                row.payload = value
            if cursor is None:
                session.add(AppStateRecord(namespace=NAMESPACE + '_cursor', record_key=gid,
                    owner_user_id=owner, payload={'last_seq': last_seq}))
            else:
                cursor.payload = {'last_seq': last_seq}
