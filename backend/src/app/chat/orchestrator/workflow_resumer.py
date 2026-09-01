from __future__ import annotations


def should_resume(workflow_state) -> bool:
    return workflow_state is not None

