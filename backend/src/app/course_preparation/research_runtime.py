"""Dedicated durable stage worker. Restart resumes the last committed checkpoint."""
import logging
from threading import Event, Thread

from .research_agent import ResearchError
from .research_repository import LostResearchLease

logger = logging.getLogger(__name__)


class ResearchRuntime:
    def __init__(self, repository, agent_factory):
        self.repository, self.agent_factory = repository, agent_factory
        self.stopping = Event()
        self.thread = None

    def run_once(self):
        claim = self.repository.claim()
        if claim is None:
            return False
        state = claim['state']
        def checkpoint(value):
            nonlocal state
            state = value
            status = self.repository.save(claim, value)
            if status == 'failed':
                raise LostResearchLease('task deadline or owner unavailable')
        try:
            agent = self.agent_factory(claim['username'], claim['config_snapshot'])
            while state.phase != 'done' and not self.stopping.is_set():
                remaining = (claim['deadline'] - self.repository.clock()).total_seconds()
                if remaining <= 0:
                    self.repository.save(claim, state, error_code='DEADLINE_EXCEEDED')
                    break
                state = agent.step(claim['request'], state, timeout=min(90, remaining), reserve=checkpoint)
                checkpoint(state)
        except LostResearchLease:
            pass  # Canceled, expired, or reclaimed: this worker cannot publish anything.
        except Exception as exc:
            code = exc.code if isinstance(exc, ResearchError) else 'RESEARCH_INTERNAL_ERROR'
            logger.warning('Research run %s stopped: %s', claim['run_id'], code)
            try:
                self.repository.save(claim, state, error_code=code)
            except LostResearchLease:
                pass
        return True

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stopping.clear()
        def poll():
            while not self.stopping.is_set():
                try:
                    worked = self.run_once()
                except Exception:
                    logger.warning('Research worker storage temporarily unavailable')
                    worked = False
                if not worked:
                    self.stopping.wait(1)
        self.thread = Thread(target=poll, name='course-research', daemon=True)
        self.thread.start()

    def stop(self, grace_seconds=10):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=grace_seconds)
