"""Privacy-aware learning context projections for chat agents."""

from __future__ import annotations

from .service import LearningService


class LearningContextReader:
    def __init__(self, service: LearningService):
        self._service = service

    def read(
        self,
        *,
        user_id: str,
        course_id: str,
        actor_role: str,
    ) -> dict:
        if str(actor_role or "").strip().lower() == "student":
            return self._service.get_student_agent_context(
                course_id=course_id,
                student_id=user_id,
                limit=10,
            )
        return self._service.get_teacher_agent_context(
            course_id=course_id,
            teacher_id=user_id,
            limit=10,
        )
