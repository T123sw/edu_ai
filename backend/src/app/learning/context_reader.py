"""Privacy-aware learning context projections for chat agents."""

from __future__ import annotations

from .service import LearningService


class LearningContextReader:
    def __init__(self, service: LearningService, assessment_service=None):
        self._service = service
        self._assessment_service = assessment_service

    def read(
        self,
        *,
        user_id: str,
        course_id: str,
        actor_role: str,
    ) -> dict:
        if str(actor_role or "").strip().lower() == "student":
            context = self._service.get_student_agent_context(
                course_id=course_id,
                student_id=user_id,
                limit=10,
            )
            if self._assessment_service is not None:
                assessments = self._assessment_service.get_student_agent_context(
                    course_id=course_id, student_id=user_id, limit=10
                )
                for group in ("pending_tasks", "completed_tasks"):
                    for task in context.get(group, []):
                        if task.get("task_id") in assessments:
                            task["assessment"] = assessments[task["task_id"]]
            return context
        context = self._service.get_teacher_agent_context(
            course_id=course_id,
            teacher_id=user_id,
            limit=10,
        )
        if self._assessment_service is not None:
            assessments = self._assessment_service.get_teacher_agent_context(
                course_id=course_id, teacher_id=user_id, limit=10
            )
            for task in context.get("task_summaries", []):
                if task.get("task_id") in assessments:
                    task["assessment"] = assessments[task["task_id"]]
        return context
