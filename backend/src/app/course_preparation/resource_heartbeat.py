"""Keep resource leases alive during rendering and other blocking work."""
from threading import Event, Thread

from .lifecycle_repository import StaleLease


class ResourceHeartbeat:
    def __init__(self, store, artifact, execution, *, interval=30):
        self.store, self.artifact, self.execution = store, artifact, execution
        self.interval = interval
        self.stopped = Event()
        self.failure = None
        self.thread = None

    def renew(self):
        if self.execution.is_cancel_requested():
            raise StaleLease('RESOURCE_EXECUTION_CANCELED')
        valid = getattr(self.execution, 'is_lease_valid', None)
        if valid is not None and not valid():
            raise StaleLease('RESOURCE_EXECUTION_LEASE_LOST')
        self.store.heartbeat(self.artifact)

    def start(self):
        self.renew()
        self.thread = Thread(target=self._run, name='preparation-resource-heartbeat', daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stopped.wait(self.interval):
            try:
                self.renew()
            except Exception as exc:
                self.failure = exc
                return

    def check(self):
        if self.failure is not None:
            raise self.failure

    def close(self):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
