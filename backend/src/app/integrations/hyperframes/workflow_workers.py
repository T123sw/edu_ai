"""Bounded asynchronous execution of intact upstream frame-worker packets."""
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import copy_context
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from uuid import uuid4


FRAME_CONCURRENCY = max(1, int(os.environ.get('HYPERFRAMES_FRAME_CONCURRENCY', '6')))
GLOBAL_CONCURRENCY = max(1, int(os.environ.get('HYPERFRAMES_GLOBAL_FRAME_CONCURRENCY', '16')))
from .stage_limits import StageSlots
GLOBAL_SLOTS = StageSlots('hyperframes-frames', GLOBAL_CONCURRENCY)


class WorkflowWorkers:
    def __init__(self, workspace, runner, guard, *, concurrency=FRAME_CONCURRENCY, slots=None):
        self.root = Path(workspace)/'.host/workers'
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner, self.guard = runner, guard
        self.slots = slots if slots is not None else GLOBAL_SLOTS
        self.executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix='hf-frame')
        self.lock = threading.RLock()
        self.stopped = threading.Event()
        self.jobs, self.identities, self.futures = {}, {}, {}

    def check(self):
        if self.stopped.is_set():
            raise RuntimeError('HYPERFRAMES_CANCELED')
        self.guard()

    def _save(self, worker_id, **values):
        with self.lock:
            self.jobs[worker_id].update(values)
            path = self.root/(worker_id+'.json')
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.jobs[worker_id], ensure_ascii=False))
            temporary.replace(path)

    def _view(self, worker_id):
        # Preserve the full native report on disk without replaying every
        # completed report into the orchestrator's context on every poll.
        row = {k:v for k,v in self.jobs[worker_id].items() if k != 'result'}
        if 'result' in self.jobs[worker_id]:
            row['result_file'] = str(self.root/(worker_id+'.json'))
        return row

    def submit(self, prompt):
        self.check()
        identity = hashlib.sha256(prompt.encode()).hexdigest()
        with self.lock:
            previous = self.identities.get(identity)
            if previous and self.jobs[previous]['status'] in ('queued', 'running', 'succeeded'):
                return self._view(previous)
            worker_id = uuid4().hex
            self.jobs[worker_id] = {'worker_id': worker_id, 'status': 'queued',
                'submitted_at': time.time(), 'prompt_sha256': identity}
            self.identities[identity] = worker_id
            self._save(worker_id)
            context = copy_context()
            self.futures[worker_id] = self.executor.submit(context.run, self._run, worker_id, prompt)
            return self._view(worker_id)

    def _run(self, worker_id, prompt):
        acquired = False
        try:
            self.check()
            while not self.slots.acquire(timeout=.2):
                self.check()
            acquired = True
            self.check()
            self._save(worker_id, status='running', started_at=time.time())
            result = self.runner(prompt, worker=True, worker_id=worker_id, cancel_event=self.stopped)
            self.check()
            self._save(worker_id, status='succeeded', result=result, finished_at=time.time())
        except Exception as exc:
            self._save(worker_id, status='canceled' if self.stopped.is_set() else 'failed',
                error=str(exc), finished_at=time.time())
        finally:
            if acquired:
                self.slots.release()

    def poll(self, worker_ids=None, *, wait_seconds=0):
        self.check()
        with self.lock:
            ids = list(self.jobs) if worker_ids is None else worker_ids
            futures = [self.futures[key] for key in ids]
        if wait_seconds and futures:
            until = time.monotonic()+min(45, max(0, wait_seconds))
            pending = futures
            while pending and time.monotonic() < until:
                self.check()
                _, pending = wait(pending, timeout=min(.5, max(0, until-time.monotonic())))
        self.check()
        with self.lock:
            return [self._view(key) for key in ids]

    def close(self):
        self.stopped.set()
        with self.lock:
            for key, future in self.futures.items():
                if future.cancel():
                    self._save(key, status='canceled', finished_at=time.time())
        self.executor.shutdown(wait=True, cancel_futures=True)
