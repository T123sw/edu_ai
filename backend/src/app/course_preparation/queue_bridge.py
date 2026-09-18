"""Reconcile SQL-ready preparations into the existing durable execution queue."""
from datetime import datetime, timezone
from threading import Event, Thread
import logging
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.database.models import CoursePreparationRecord as Prep, CoursePreparationAttemptRecord as Attempt
from .runtime_models import PreparationExecution as Run, PreparationBudget as Budget
from .repository import aware
from .tool_registry import digest

logger = logging.getLogger(__name__)


class PreparationQueueBridge:
    def __init__(self, repository, task_store):
        self.repository, self.task_store = repository, task_store
        self.stop_event = Event()
        self.thread = None

    def reconcile(self):
        now = self.repository.clock()
        with Session(self.repository.engine) as session:
            rows = session.execute(select(Prep.preparation_id, Prep.owner_user_id, Prep.current_attempt_no,
                Prep.revision, Budget.deadline).join(Attempt, (Attempt.preparation_id == Prep.preparation_id) &
                (Attempt.attempt_no == Prep.current_attempt_no)).join(Run, (Run.preparation_id == Prep.preparation_id) &
                (Run.attempt_no == Attempt.attempt_no)).join(Budget, Budget.preparation_id == Prep.preparation_id)
                .where(Attempt.status.in_(('accepted', 'running', 'checking')), Run.wake_at <= now,
                       or_(Run.lease_until.is_(None), Run.lease_until <= now)).limit(100)).all()
        for prep_id, owner, attempt, revision, deadline in rows:
            # The time bucket permits re-dispatch if a queue ticket failed before claiming SQL.
            # SQL leases remain authoritative: duplicate tickets can never execute concurrently.
            key = digest([prep_id, attempt, revision, int(now.timestamp() // 30)])
            self.task_store.enqueue(task_id='prepstep_' + key[:32], workflow_type='preparation_step',
                handler_version=1, owner_user_id=owner, course_id=None, scope_type='preparation', scope_id=prep_id,
                command={'preparation_id': prep_id}, config_snapshot_id=None, idempotency_key=key,
                max_attempts=3, deadline_at=max(aware(deadline).timestamp(), now.timestamp() + 180))
        return len(rows)

    def wake(self, preparation_id):
        # SQL is already committed. A queue outage is recovered by periodic reconciliation.
        try:
            self.reconcile()
        except Exception:
            logger.warning('Preparation queue reconciliation deferred')

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        def poll():
            while not self.stop_event.is_set():
                self.wake(None)
                self.stop_event.wait(1)
        self.thread = Thread(target=poll, daemon=True, name='preparation-queue-bridge')
        self.thread.start()

    def stop(self, grace_seconds=5):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=grace_seconds)
