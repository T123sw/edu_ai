"""A queue task executes one bounded stage step, then releases its worker slot."""
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Thread
from .lifecycle_repository import BudgetExceeded, NoProgress, StaleLease


@dataclass(frozen=True)
class StepResult:
    checkpoint: dict
    next_stage: str | None = None
    reason: str | None = None
    wait_seconds: int = 0


class PreparationRunner:
    def __init__(self, repository, handlers, *, capabilities=()):
        self.repository, self.handlers = repository, dict(handlers)
        self.capabilities = tuple(capabilities)

    def run_step(self, preparation_id, *, worker_id, canceled=lambda: False, expected_owner=None):
        if expected_owner is not None:
            self.repository.get_public(expected_owner, preparation_id)
        context = self.repository.claim(worker_id, preparation_id=preparation_id, capabilities=self.capabilities)
        if context is None:
            return {'claimed': False}
        stop = Event()
        def heartbeat():
            while not stop.wait(30):
                try:
                    if canceled():
                        return
                    self.repository.heartbeat(context)
                except (StaleLease, PermissionError, BudgetExceeded):
                    return
        keeper = Thread(target=heartbeat, daemon=True)
        keeper.start()
        try:
            if canceled():
                self.repository.cancel(context.owner_user_id, preparation_id)
                return {'canceled': True}
            handler = self.handlers.get(context.stage)
            if handler is None:
                raise ValueError('STAGE_HANDLER_UNAVAILABLE')
            if context.deadline and datetime.fromisoformat(context.deadline) <= datetime.now(timezone.utc):
                raise BudgetExceeded('DEADLINE_EXCEEDED')
            result = handler(context)
            if not isinstance(result, StepResult):
                raise ValueError('INVALID_STAGE_RESULT')
            if canceled():
                self.repository.cancel(context.owner_user_id, preparation_id)
                return {'canceled': True}
            self.repository.checkpoint(context, result.checkpoint)
            if result.next_stage:
                context = self.repository.transition(context, result.next_stage, reason=result.reason)
            self.repository.release(context, delay_seconds=result.wait_seconds)
            return {'claimed': True, 'stage': context.stage, 'waiting': result.wait_seconds > 0}
        except StaleLease:
            return {'stale': True}
        except Exception as exc:
            code = ('BUDGET_EXHAUSTED' if isinstance(exc, BudgetExceeded) else
                    'NO_PROGRESS' if isinstance(exc, NoProgress) else
                    'SOURCE_OR_OWNER_UNAVAILABLE' if isinstance(exc, PermissionError) else 'STEP_FAILED')
            try:
                self.repository.fail(context, code)
            except StaleLease:
                pass
            return {'failed': True, 'code': code}
        finally:
            stop.set()
            keeper.join(timeout=1)


class PreparationStepHandler:
    def __init__(self, runner_factory):
        self.runner_factory = runner_factory

    def __call__(self, command, context):
        result = self.runner_factory().run_step(command['preparation_id'], worker_id=context.task_id,
                                               canceled=context.is_cancel_requested, expected_owner=context.owner_user_id)
        # This is an execution receipt, never a course delivery receipt.
        return {'saved': True, 'result_ref': {'kind': 'preparation_step', **result}}
