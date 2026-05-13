from __future__ import annotations

__all__ = ["LessonPlanWorkflowRuntime"]


def __getattr__(name: str):
    if name == "LessonPlanWorkflowRuntime":
        from .runtime import LessonPlanWorkflowRuntime

        return LessonPlanWorkflowRuntime
    raise AttributeError(name)
