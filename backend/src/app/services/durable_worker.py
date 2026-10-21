"""Additional persistent workers sharing PostgreSQL leases with the API process."""
from __future__ import annotations

import argparse
import logging
import signal
import threading
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--control-workers', type=int, default=2)
    parser.add_argument('--light-workers', type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from app.chat.tasks.postgres_task_store import PostgresTaskStore
    from app.chat.tasks.task_store import get_task_store
    from app.course_preparation.application import start_for_app
    from app.services.durable_job_runtime import build_durable_job_runtime

    store = get_task_store()
    if not isinstance(store, PostgresTaskStore):
        raise RuntimeError('Additional workers require the shared PostgreSQL task store')
    from app.integrations.hyperframes.build_info import runtime_info
    logging.info('Generation build: %s', runtime_info())
    runtime = build_durable_job_runtime(task_store=store, worker_count=args.workers,
                                        control_worker_count=args.control_workers, light_worker_count=args.light_workers,
                                        exclude_control_from_general=True)
    preparation = start_for_app(SimpleNamespace(state=SimpleNamespace()), store)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        # The API already reconciles public jobs. Joining an active queue must
        # not run startup repairs against tasks owned by another live process.
        runtime.executor.start()
        logging.info('Additional workers ready: generation=%s control=%s ids=%s',
                     args.workers, args.control_workers, runtime.executor.worker_ids)
        stop.wait()
    finally:
        if preparation:
            preparation.stop()
        # Stop claiming first; let already leased work finish with heartbeats.
        stuck = runtime.executor.stop(timeout_seconds=3600)
        if stuck:
            logging.warning('Workers still draining at shutdown deadline: %s', stuck)


if __name__ == '__main__':
    main()
