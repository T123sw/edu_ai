from __future__ import annotations


def allow_rag(policy) -> bool:
    return bool(getattr(policy, "allow_rag", False))


def allow_web(policy) -> bool:
    return bool(getattr(policy, "allow_web", False))
