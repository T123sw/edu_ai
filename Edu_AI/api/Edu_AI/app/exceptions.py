"""Bootstrap-local exception helpers."""

from __future__ import annotations


def log_bootstrap_exception(stage: str, exc: Exception) -> None:
    print(f"[Bootstrap] {stage} skipped: {exc}")

