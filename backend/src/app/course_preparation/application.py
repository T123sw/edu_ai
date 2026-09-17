"""Lifecycle composition; production enables it only with a complete stage pipeline."""
import os
from .lifecycle_repository import LifecycleRepository
from .queue_bridge import PreparationQueueBridge
from .runner import PreparationRunner
from .service import PreparationService

_active = None


class PreparationApplication:
    def __init__(self, repository, task_store, handlers, *, capabilities=()):
        self.repository = repository
        self.runner = PreparationRunner(repository, handlers, capabilities=capabilities)
        self.bridge = PreparationQueueBridge(repository, task_store)
        self.service = PreparationService(repository, wake=self.bridge.wake)

    def start(self):
        self.bridge.start()

    def stop(self, grace_seconds=5):
        self.bridge.stop(grace_seconds)


def application():
    if _active is None:
        raise RuntimeError('PREPARATION_PIPELINE_NOT_STARTED')
    return _active


def start_for_app(app, task_store):
    global _active
    if os.getenv('COURSE_PREPARATION_ENABLED', '').lower() not in ('1', 'true', 'yes'):
        return None
    # Concrete input/generation/delivery stage adapters are installed by P3-P5.
    from .pipeline import build_pipeline
    built = build_pipeline(task_store)
    required = {'normalize', 'ingest', 'research_scope', 'plan', 'research_nodes', 'produce', 'review', 'repair', 'commit'}
    if set(built.runner.handlers) != required:
        raise RuntimeError('PREPARATION_PIPELINE_INCOMPLETE')
    _active = built
    app.state.preparation_service = built.service
    built.start()
    return built
