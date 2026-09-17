"""Owner-scoped SQL checkpoints with fenced worker leases and idempotent intake."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import CourseResearchRunRecord as Run, User
from .contracts import IdempotencyConflict, PreparationNotFound
from .repository import aware
from .research_contracts import ResearchRequest, ResearchState
from .schemas import request_digest


class LostResearchLease(RuntimeError):
    pass


class ResearchRepository:
    def __init__(self, engine, *, clock=lambda: datetime.now(timezone.utc)):
        self.engine, self.clock = engine, clock

    @staticmethod
    def _user(session, username):
        user = session.scalar(select(User).where(User.username == username, User.is_disabled.is_(False)))
        if user is None:
            raise PreparationNotFound('active owner not found')
        return user

    @staticmethod
    def public(row):
        state = ResearchState.model_validate(row.state_payload)
        result = None
        if row.status == 'succeeded':
            path = state.path.model_dump(mode='json')
            ids = {node['node_key']: 'pathnode_' + uuid5(NAMESPACE_URL, row.run_id + ':' + node['node_key']).hex
                   for node in path['nodes']}
            for node in path['nodes']:
                node['node_id'] = ids[node['node_key']]
                node['prerequisite_ids'] = [ids[key] for key in node['prerequisite_keys']]
            result = {'brief': state.brief.model_dump(mode='json'),
                      'research_summary': state.summary.model_dump(mode='json'), 'learning_path': path,
                      'sources': [e.model_dump(exclude={'content', 'candidate_id'}) for e in state.evidence],
                      'review': state.review.model_dump(mode='json')}
        return {'run_id': row.run_id, 'purpose': 'research_learning_path', 'course_ready': False,
                'status': row.status, 'stage': state.phase, 'revision': row.revision,
                'created_at': aware(row.created_at).isoformat(), 'updated_at': aware(row.updated_at).isoformat(),
                'progress': {'model_calls': state.calls, 'searches': state.searches,
                             'sources_read': len(state.evidence), 'repairs': state.repairs},
                'error_code': row.error_code, 'result': result}

    def submit(self, username, request, *, config_snapshot=None):
        request = ResearchRequest.model_validate(request.model_dump(mode='json'))
        digest = request_digest(request)
        def existing(session, owner):
            row = session.scalar(select(Run).where(Run.owner_user_id == owner, Run.request_id == str(request.request_id)))
            if row is not None and row.request_sha256 != digest:
                raise IdempotencyConflict('request_id 已用于不同需求')
            return row
        try:
            with Session(self.engine) as session, session.begin():
                user = self._user(session, username)
                row = existing(session, user.user_id)
                if row is not None:
                    return self.public(row)
                now = self.clock()
                row = Run(run_id='research_' + uuid4().hex, owner_user_id=user.user_id,
                    request_id=str(request.request_id), request_sha256=digest,
                    request_payload=request.model_dump(mode='json'), config_snapshot=config_snapshot or {},
                    state_payload=ResearchState().model_dump(mode='json'), status='queued', revision=1,
                    recoveries=0, created_at=now, updated_at=now, deadline=now + timedelta(seconds=600))
                session.add(row)
                session.flush()
                return self.public(row)
        except IntegrityError:
            with Session(self.engine) as session:
                row = existing(session, self._user(session, username).user_id)
                if row is None:
                    raise
                return self.public(row)

    def get(self, username, run_id, *, cancel=False):
        with Session(self.engine) as session, session.begin():
            owner = self._user(session, username).user_id
            row = session.scalar(select(Run).where(Run.run_id == run_id, Run.owner_user_id == owner).with_for_update())
            if row is None:
                raise PreparationNotFound('research run not found')
            if cancel and row.status in ('queued', 'running'):
                row.status, row.lease_token, row.lease_until = 'canceled', None, None
                row.revision += 1
                row.updated_at = self.clock()
            return self.public(row)

    def claim(self):
        now = self.clock()
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(Run).where(or_(Run.status == 'queued',
                (Run.status == 'running') & (Run.lease_until <= now)))
                .order_by(Run.created_at).with_for_update(skip_locked=True).limit(1))
            if row is None:
                return None
            user = session.get(User, row.owner_user_id)
            if aware(row.deadline) <= now or row.recoveries >= 3 or user is None or user.is_disabled:
                row.status, row.error_code = 'failed', 'DEADLINE_OR_RECOVERY_LIMIT' if user and not user.is_disabled else 'OWNER_UNAVAILABLE'
                row.lease_token, row.lease_until = None, None
                row.revision += 1
                row.updated_at = now
                return None
            if row.status == 'running':
                row.recoveries += 1
            row.status, row.lease_token = 'running', uuid4().hex
            row.lease_until = now + timedelta(seconds=150)
            row.updated_at, row.revision = now, row.revision + 1
            return {'run_id': row.run_id, 'lease_token': row.lease_token, 'username': user.username,
                    'config_snapshot': row.config_snapshot, 'deadline': aware(row.deadline),
                    'request': ResearchRequest.model_validate(row.request_payload),
                    'state': ResearchState.model_validate(row.state_payload)}

    def save(self, claim, state, *, error_code=None):
        now = self.clock()
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(Run).where(Run.run_id == claim['run_id']).with_for_update())
            if row is None or row.status != 'running' or row.lease_token != claim['lease_token'] or aware(row.lease_until) <= now:
                raise LostResearchLease('research lease is no longer valid')
            user = session.get(User, row.owner_user_id)
            if user is None or user.is_disabled:
                error_code = 'OWNER_UNAVAILABLE'
            elif aware(row.deadline) <= now:
                error_code = 'DEADLINE_EXCEEDED'
            state = ResearchState.model_validate(state.model_dump(mode='json'))
            if state.phase == 'done' and (not state.path or not state.summary or not state.review or state.review.decision != 'pass'):
                raise ValueError('cannot publish unreviewed research')
            row.state_payload = state.model_dump(mode='json')
            row.revision += 1
            row.updated_at = now
            row.lease_until = now + timedelta(seconds=150)
            if error_code or state.phase == 'done':
                row.status = 'failed' if error_code else 'succeeded'
                row.error_code, row.lease_token, row.lease_until = error_code, None, None
            return row.status
