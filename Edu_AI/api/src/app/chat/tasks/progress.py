"""Thread-local progress callback registry.

background_runner sets a callback per task before calling workflow.run().
Long-running sub-processes (e.g. PPT polling loop) call report_progress()
to surface intermediate state through the task store without coupling to
the task_id or TaskStore directly.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional

_local = threading.local()


def set_progress_callback(callback: Callable[[dict], None]) -> None:
    _local.cb = callback


def clear_progress_callback() -> None:
    _local.cb = None


def report_progress(progress: dict[str, Any]) -> None:
    cb: Optional[Callable] = getattr(_local, "cb", None)
    if cb is None:
        return
    try:
        cb(progress)
    except Exception:
        pass
