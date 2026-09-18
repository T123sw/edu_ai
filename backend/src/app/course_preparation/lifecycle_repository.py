"""Full preparation lifecycle; one transaction owns each state/accounting mutation."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.database.models import (CoursePreparationRecord as Prep, CoursePreparationAttemptRecord as Attempt,
                                 CoursePreparationEventRecord as Event, User)
from .repository import PreparationRepository, aware
from .contracts import PreparationEvent
from .runtime_models import PreparationExecution as Run, PreparationBudget as Budget, PreparationAction as Action
from .runtime_contracts import BudgetCost, BudgetLimits, ExecutionContext
from .schemas import PreparationRequest, request_digest
from .tool_registry import digest


class StaleLease(RuntimeError): pass
class BudgetExceeded(RuntimeError): pass
class RevisionConflict(ValueError): pass
class NoProgress(RuntimeError): pass


TRANSITIONS = {
    'normalize': {'ingest', 'research_scope'}, 'ingest': {'research_scope'},
    'research_scope': {'plan'}, 'plan': {'research_scope', 'research_nodes'},
    'research_nodes': {'produce', 'research_scope'}, 'produce': {'review'}, 'review': {'repair', 'commit'},
    'repair': {'research_nodes', 'produce', 'review'}, 'commit': set(),
}
REQUIRED = {'ingest': 'brief', 'research_scope': 'brief', 'plan': 'research_summary',
            'research_nodes': 'plan', 'produce': 'node_evidence', 'review': 'artifacts', 'commit': 'quality'}
ACTIVE = ('accepted', 'running', 'checking')


class LifecycleRepository(PreparationRepository):
    def __init__(self, engine, *, authorizer, clock=None):
        super().__init__(engine, authorizer=authorizer)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def initialize(self, session, record, options=None):
        options = options or {}
        limits = BudgetLimits.model_validate(options.get('limits', {}))
        now = self.clock()
        session.add(Budget(preparation_id=record.preparation_id, deadline=now + timedelta(seconds=limits.seconds),
            limits=limits.model_dump(), reserved=BudgetCost().model_dump(), consumed=BudgetCost().model_dump()))
        session.add(Run(preparation_id=record.preparation_id, attempt_no=1, wake_at=now,
                        input_digest=record.request_sha256, checkpoint={'config_snapshot': options.get('config_snapshot', {})},
                        no_progress=0))

    def submit(self, owner, request, *, limits=None, config_snapshot=None):
        value = self.accept(owner_user_id=owner, request=request, runtime_options={
            'limits': (limits or BudgetLimits()).model_dump(), 'config_snapshot': config_snapshot or {}})
        return self.get_public(owner, value.preparation_id)

    def _owner(self, session, owner, preparation_id):
        row = self._owned_record(session, owner, preparation_id)
        if session.get(Run, (preparation_id, row.current_attempt_no)) is None:
            from .contracts import PreparationNotFound
            raise PreparationNotFound(preparation_id)
        user = session.get(User, owner)
        if user is None or user.is_disabled:
            raise PermissionError('owner unavailable')
        return row

    def _event(self, session, prep, attempt, kind, payload=None):
        # Every transition locks Prep, which serializes both revision and event sequence.
        prep.revision += 1
        last = session.scalar(select(Event.sequence).where(Event.preparation_id == prep.preparation_id)
                              .order_by(Event.sequence.desc()).limit(1)) or 0
        session.add(Event(event_id='pevt_' + uuid4().hex, preparation_id=prep.preparation_id,
                          attempt_no=attempt.attempt_no, sequence=last + 1, event_type=kind,
                          revision=prep.revision, payload=payload or {}, occurred_at=self.clock()))
        session.flush()

    def _locked(self, session, context, *, authorize=True, allow_expired_deadline=False):
        prep = session.scalar(select(Prep).where(Prep.preparation_id == context.preparation_id).with_for_update())
        if prep is None or prep.current_attempt_no != context.attempt_no:
            raise StaleLease('STALE_LEASE')
        attempt = session.get(Attempt, (prep.preparation_id, context.attempt_no))
        run = session.get(Run, (prep.preparation_id, context.attempt_no))
        if (run is None or attempt.status not in ACTIVE or run.lease_token != context.lease_token
                or run.lease_until is None or aware(run.lease_until) <= self.clock()):
            raise StaleLease('STALE_LEASE')
        if prep.owner_user_id != context.owner_user_id or run.input_digest != prep.request_sha256:
            raise StaleLease('CHECKPOINT_INPUT_CHANGED')
        budget = session.get(Budget, prep.preparation_id)
        if not allow_expired_deadline and aware(budget.deadline) <= self.clock():
            raise BudgetExceeded('DEADLINE_EXCEEDED')
        if authorize:
            self.authorizer.authorize(prep.owner_user_id, PreparationRequest.model_validate(prep.request_payload))
        return prep, attempt, run, budget

    def get_public(self, owner, preparation_id):
        with Session(self.engine) as session:
            prep = self._owner(session, owner, preparation_id)
            attempt = session.get(Attempt, (preparation_id, prep.current_attempt_no))
            run = session.get(Run, (preparation_id, prep.current_attempt_no))
            budget = session.get(Budget, preparation_id)
            return {'preparation_id': preparation_id, 'attempt_no': attempt.attempt_no, 'status': attempt.status,
                    'stage': attempt.stage, 'revision': prep.revision, 'error_code': run.error_code,
                    'result_ref': run.result_ref if attempt.status == 'succeeded' else None,
                    'budget': {'limits': budget.limits, 'reserved': budget.reserved, 'consumed': budget.consumed,
                               'deadline': aware(budget.deadline).isoformat()}}

    def events(self, *, owner_user_id, preparation_id, after=0, limit=100):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError('invalid event cursor or page size')
        with Session(self.engine) as session:
            self._owner(session, owner_user_id, preparation_id)
            rows = session.scalars(select(Event).where(Event.preparation_id == preparation_id,
                Event.sequence > after).order_by(Event.sequence).limit(limit)).all()
            return [PreparationEvent(event_id=row.event_id, preparation_id=preparation_id,
                attempt_no=row.attempt_no, sequence=row.sequence, type=row.event_type, revision=row.revision,
                occurred_at=aware(row.occurred_at), payload=row.payload) for row in rows]

    def claim(self, worker_id, *, preparation_id=None, capabilities=()):
        now = self.clock()
        with Session(self.engine) as session, session.begin():
            query = (select(Prep, Attempt, Run).join(Attempt, (Attempt.preparation_id == Prep.preparation_id) &
                (Attempt.attempt_no == Prep.current_attempt_no)).join(Run, (Run.preparation_id == Prep.preparation_id) &
                (Run.attempt_no == Attempt.attempt_no)).where(Attempt.status.in_(ACTIVE), Run.wake_at <= now,
                or_(Run.lease_until.is_(None), Run.lease_until <= now)))
            if preparation_id:
                query = query.where(Prep.preparation_id == preparation_id)
            record = session.execute(query.order_by(Run.wake_at, Prep.created_at)
                                     .with_for_update(skip_locked=True).limit(1)).first()
            if record is None:
                return None
            prep, attempt, run = record
            budget = session.get(Budget, prep.preparation_id)
            error = None
            try:
                self.authorizer.authorize(prep.owner_user_id, PreparationRequest.model_validate(prep.request_payload))
            except (PermissionError, LookupError):
                error = 'SOURCE_OR_OWNER_UNAVAILABLE'
            except RevisionConflict:
                error = 'MANIFEST_BASE_CHANGED'
            if aware(budget.deadline) <= now:
                error = 'DEADLINE_EXCEEDED'
            if run.input_digest != prep.request_sha256:
                error = 'CHECKPOINT_INPUT_CHANGED'
            if error:
                attempt.status, run.error_code = 'failed', error
                run.lease_token, run.lease_until = None, None
                self._event(session, prep, attempt, 'failed', {'code': error})
                return None
            was_accepted = attempt.status == 'accepted'
            attempt.status = 'running' if attempt.stage != 'review' else 'checking'
            run.lease_token, run.worker_id = uuid4().hex, worker_id
            run.lease_until = now + timedelta(seconds=150)
            if was_accepted:
                self._event(session, prep, attempt, 'stage_changed', {'stage': attempt.stage})
            return ExecutionContext(preparation_id=prep.preparation_id, attempt_no=attempt.attempt_no,
                owner_user_id=prep.owner_user_id, lease_token=run.lease_token, revision=prep.revision,
                stage=attempt.stage, operation=prep.operation, source_policy=prep.request_payload['source_policy']['mode'],
                checkpoint=run.checkpoint, capabilities=tuple(capabilities), deadline=aware(budget.deadline).isoformat())

    def checkpoint(self, context, value, *, count_no_progress=True):
        with Session(self.engine) as session, session.begin():
            prep, attempt, run, budget = self._locked(session, context)
            if count_no_progress and digest(run.checkpoint) == digest(value):
                if run.no_progress >= 2:
                    raise NoProgress('NO_PROGRESS')
                run.no_progress += 1
            else:
                run.no_progress = 0
            run.checkpoint = value
            run.lease_until = self.clock() + timedelta(seconds=150)
            prep.revision += 1

    def restart_for_memory(self, context, subject):
        from app.chat.memory.lifecycle import lock_epoch
        with Session(self.engine) as session, session.begin():
            watermark = lock_epoch(session, subject)
            prep, attempt, run, _ = self._locked(session, context)
            previous = run.checkpoint
            state = dict(previous.get('research_state', {}))
            # Preserve spent decisions, reads, evidence and action ledger. Rebuild
            # only derived context; completed old child outputs remain drafts.
            state.update(phase='intent', brief=None, summary=None, path=None, review=None, errors=0, last_error=None)
            discarded = {key:previous[key] for key in ('plan','artifacts','quality','memory_refs') if key in previous}
            run.checkpoint = {key:previous[key] for key in ('config_snapshot','ingested_documents','input_documents') if key in previous}
            run.checkpoint.update(research_state=state, invalidated_drafts=[*previous.get('invalidated_drafts', []), discarded],
                                  context_rebuild_epoch=watermark.epoch)
            attempt.stage = 'normalize'
            attempt.status = 'running'
            run.no_progress = 0
            run.lease_token, run.lease_until, run.worker_id = None, None, None
            run.wake_at = self.clock()
            self._event(session, prep, attempt, 'stage_changed', {'stage':'normalize','reason':'MEMORY_DEPENDENCY_CHANGED'})

    def heartbeat(self, context):
        with Session(self.engine) as session, session.begin():
            _, _, run, _ = self._locked(session, context)
            run.lease_until = self.clock() + timedelta(seconds=150)

    def release(self, context, *, delay_seconds=0):
        with Session(self.engine) as session, session.begin():
            _, _, run, _ = self._locked(session, context)
            run.lease_token, run.lease_until, run.worker_id = None, None, None
            run.wake_at = self.clock() + timedelta(seconds=max(0, min(delay_seconds, 300)))

    def transition(self, context, stage, *, reason=None):
        with Session(self.engine) as session, session.begin():
            prep, attempt, run, _ = self._locked(session, context)
            if stage not in TRANSITIONS.get(attempt.stage, set()):
                raise ValueError('ILLEGAL_STAGE_TRANSITION')
            required = REQUIRED.get(stage)
            retained_review=(stage=='review' and prep.request_payload.get('operation')=='adjust_course'
                and bool(run.checkpoint.get('retained_node_ids')) and run.checkpoint.get('resource_specs')==[]
                and set(run.checkpoint['retained_node_ids'])=={n['node_key'] for n in run.checkpoint.get('plan',{}).get('nodes',[])})
            if required and not run.checkpoint.get(required) and not retained_review:
                raise ValueError('STAGE_PREREQUISITE_MISSING:' + required)
            if stage == 'research_scope' and attempt.stage == 'normalize':
                if prep.request_payload.get('uploads') or not reason:
                    raise ValueError('INGEST_REQUIRED_OR_SKIP_REASON_MISSING')
            if stage == 'commit' and run.checkpoint['quality'].get('decision') != 'pass':
                raise ValueError('QUALITY_NOT_PASSED')
            attempt.stage = stage
            attempt.status = 'checking' if stage == 'review' else 'running'
            self._event(session, prep, attempt, 'stage_changed', {'stage': stage, 'reason': reason})
            return context.model_copy(update={'stage': stage, 'revision': prep.revision, 'checkpoint': run.checkpoint})

    def fail(self, context, code):
        with Session(self.engine) as session, session.begin():
            prep, attempt, run, _ = self._locked(session, context, authorize=False, allow_expired_deadline=True)
            attempt.status, run.error_code = 'failed', code
            run.lease_token, run.lease_until = None, None
            self._event(session, prep, attempt, 'failed', {'code': code})

    def cancel(self, owner, preparation_id, *, expected_revision=None):
        with Session(self.engine) as session, session.begin():
            prep = session.scalar(select(Prep).where(Prep.preparation_id == preparation_id).with_for_update())
            self._owner(session, owner, preparation_id)
            if expected_revision is not None and prep.revision != expected_revision:
                raise RevisionConflict('REVISION_CONFLICT')
            attempt = session.get(Attempt, (preparation_id, prep.current_attempt_no))
            run = session.get(Run, (preparation_id, prep.current_attempt_no))
            if attempt.status in ACTIVE:
                self._event(session, prep, attempt, 'cancel_requested')
                attempt.status, run.lease_token, run.lease_until = 'canceled', None, None
                self._event(session, prep, attempt, 'canceled')
        return self.get_public(owner, preparation_id)

    def retry(self, owner, preparation_id):
        with Session(self.engine) as session, session.begin():
            prep = session.scalar(select(Prep).where(Prep.preparation_id == preparation_id).with_for_update())
            self._owner(session, owner, preparation_id)
            self.authorizer.authorize(owner, PreparationRequest.model_validate(prep.request_payload))
            old = session.get(Attempt, (preparation_id, prep.current_attempt_no))
            budget = session.get(Budget, preparation_id)
            if old.status not in ('failed', 'canceled'):
                raise ValueError('ONLY_TERMINAL_FAILURE_CAN_RETRY')
            if aware(budget.deadline) <= self.clock():
                raise BudgetExceeded('DEADLINE_EXCEEDED')
            previous = session.get(Run, (preparation_id, old.attempt_no))
            prep.current_attempt_no += 1
            new = Attempt(preparation_id=preparation_id, attempt_no=prep.current_attempt_no,
                          status='accepted', stage=old.stage, created_at=self.clock())
            session.add(new)
            session.flush()
            session.add(Run(preparation_id=preparation_id, attempt_no=new.attempt_no, wake_at=self.clock(),
                            input_digest=prep.request_sha256, checkpoint=previous.checkpoint, no_progress=0))
            self._event(session, prep, new, 'accepted', {'retry_of': old.attempt_no})
        return self.get_public(owner, preparation_id)

    def begin_action(self, context, key, kind, payload, cost):
        cost = BudgetCost.model_validate(cost.model_dump())
        with Session(self.engine) as session, session.begin():
            prep, _, _, budget = self._locked(session, context)
            return self._reserve_action(session, prep, budget, key, kind, payload, cost)

    def _reserve_action(self, session, prep, budget, key, kind, payload, cost):
        old = session.scalar(select(Action).where(Action.preparation_id == prep.preparation_id, Action.action_key == key))
        if old:
            if old.kind != kind or old.payload_digest != digest(payload):
                raise ValueError('ACTION_PAYLOAD_CONFLICT')
            return self._action_view(old, replay=True)
        limits, reserved, consumed = budget.limits, dict(budget.reserved), budget.consumed
        for metric, amount in cost.model_dump().items():
            if consumed[metric] + reserved[metric] + amount > limits[metric]:
                raise BudgetExceeded('BUDGET_EXHAUSTED:' + metric)
            reserved[metric] += amount
        budget.reserved = reserved
        action = Action(action_id='paction_' + uuid4().hex, preparation_id=prep.preparation_id,
                        action_key=key, kind=kind, payload_digest=digest(payload), payload=payload,
                        reserved=cost.model_dump(), status='pending', created_at=self.clock())
        session.add(action)
        session.flush()
        return self._action_view(action, replay=False)


    @staticmethod
    def _action_view(action, replay):
        return {'action_id': action.action_id, 'status': action.status, 'receipt': action.receipt,
                'replay': replay, 'reserved': action.reserved}

    def finish_action(self, context, action_id, receipt, actual=None, *, failed=False):
        with Session(self.engine) as session, session.begin():
            prep, attempt, _, budget = self._locked(session, context)
            return self._settle_action(session, prep, attempt, budget, action_id, receipt, actual, failed=failed)

    def _settle_action(self, session, prep, attempt, budget, action_id, receipt, actual=None, *, failed=False):
        action = session.get(Action, action_id)
        if action is None or action.preparation_id != prep.preparation_id:
            raise ValueError('ACTION_NOT_OWNED')
        if action.status != 'pending':
            if action.receipt != receipt:
                raise ValueError('ACTION_RECEIPT_CONFLICT')
            return action.receipt
        spent = (BudgetCost.model_validate(actual.model_dump()).model_dump() if actual else action.reserved)
        reserved, consumed = dict(budget.reserved), dict(budget.consumed)
        for metric, amount in spent.items():
            if amount > action.reserved[metric]:
                raise BudgetExceeded('USAGE_EXCEEDS_RESERVED_UPPER_BOUND')
            reserved[metric] -= action.reserved[metric]
            consumed[metric] += amount
        budget.reserved, budget.consumed = reserved, consumed
        action.status, action.receipt, action.consumed = ('failed' if failed else 'completed'), receipt, spent
        self._event(session, prep, attempt, 'child_updated', {'action_id': action_id, 'status': action.status})
        return receipt
