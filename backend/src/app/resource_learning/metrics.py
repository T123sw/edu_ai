from __future__ import annotations

from collections import Counter
from threading import Lock


class ResourceLearningMetrics:
    """Low-cardinality in-process counters; labels never contain student IDs."""

    def __init__(self):
        self._values: Counter[tuple[str, str]] = Counter()
        self._lock = Lock()

    def increment(self, metric: str, *, outcome: str = "ok", value: int = 1) -> None:
        with self._lock:
            self._values[(metric, outcome)] += value

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                f"{metric}:{outcome}": value
                for (metric, outcome), value in sorted(self._values.items())
            }


resource_learning_metrics = ResourceLearningMetrics()
