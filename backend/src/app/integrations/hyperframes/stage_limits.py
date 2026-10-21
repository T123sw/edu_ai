"""Single-host, cross-process admission. Kernel locks recover on process exit.

All services must share EDU_STAGE_LIMIT_DIR and the same limits. No credentials
or media are stored here. Multi-host deployments need a shared admission service.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import fcntl
import hashlib
import json
import os
from pathlib import Path
import threading
import time


ADMISSION_GUARD = ContextVar('admission_guard', default=lambda: None)

def limit_root():
    root = Path(os.environ.get('EDU_STAGE_LIMIT_DIR', f'/tmp/edu-ai-stage-limits-{os.getuid()}'))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


class StageSlots:
    def __init__(self, name, capacity, *, root=None):
        self.root = Path(root) if root is not None else limit_root()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.name = hashlib.sha256(name.encode()).hexdigest()
        self.capacity = max(1, int(capacity))
        self.local = threading.local()

    def acquire(self, blocking=True, timeout=None):
        if getattr(self.local, 'file', None) is not None:
            raise RuntimeError('Stage slot is not reentrant')
        deadline = None if timeout is None else time.monotonic() + max(0, timeout)
        while True:
            for index in range(self.capacity):
                handle = (self.root / f'{self.name}.{index}.lock').open('a+b')
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    handle.close()
                    continue
                self.local.file = handle
                return True
            if not blocking or deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(.05 if deadline is None else min(.05, max(0, deadline - time.monotonic())))

    def release(self):
        handle = getattr(self.local, 'file', None)
        if handle is None:
            raise RuntimeError('No stage slot held by this thread')
        self.local.file = None
        handle.close()

    def fileno(self):
        return self.local.file.fileno()

    @contextmanager
    def hold(self, guard=lambda: None):
        guard()
        while not self.acquire(timeout=.2):
            guard()
        try:
            guard()
            yield self
        finally:
            self.release()


class ProviderRate:
    """Serialize request starts and share provider cooldown across processes."""
    def __init__(self, name, *, interval=.25, root=None):
        self.root = Path(root) if root is not None else limit_root()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / (hashlib.sha256(name.encode()).hexdigest() + '.rate')
        self.interval = max(0, float(interval))

    def _update(self, cooldown=None):
        # Keep a separate, stable lock inode across atomic JSON replacements.
        with self.path.with_suffix('.rate.lock').open('a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = json.loads(self.path.read_text()) if self.path.exists() else {}
            now = time.time()
            if cooldown is not None:
                state['cooldown_until'] = max(state.get('cooldown_until', 0), now + max(0, cooldown))
                delay = 0
            else:
                delay = max(state.get('next_start', 0), state.get('cooldown_until', 0)) - now
                if delay > 0:
                    return delay
                state['next_start'] = now + self.interval
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            temporary.replace(self.path)
            return max(0, delay)

    def try_start(self):
        return self._update()

    def cool_down(self, seconds):
        self._update(seconds)
