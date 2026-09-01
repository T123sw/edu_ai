from __future__ import annotations

import json

from app.learning.context_reader import LearningContextReader
from test_assessment_attempt_service import _answers, _service


def test_agent_context_is_role_scoped_and_never_leaks_unrevealed_solutions(tmp_path):
    assessment, task = _service(tmp_path)
    attempt = assessment.start_attempt(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    assessment.save_answers(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        answers=_answers(2),
        expected_revision=0,
    )
    assessment.submit_attempt(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        idempotency_key="agent-projection-submit",
    )
    reader = LearningContextReader(assessment.learning_service, assessment)

    student = reader.read(
        user_id="student-1", course_id="course-1", actor_role="student"
    )
    student_payload = json.dumps(student, ensure_ascii=False)
    assert student["pending_tasks"][0]["assessment"]["result"] == "needs_retry"
    assert student["pending_tasks"][0]["assessment"]["remaining_attempts"] == 2
    assert "scoring_key" not in student_payload
    assert "solution" not in student_payload

    teacher = reader.read(
        user_id="teacher-1", course_id="course-1", actor_role="teacher"
    )
    teacher_payload = json.dumps(teacher, ensure_ascii=False)
    report = teacher["task_summaries"][0]["assessment"]
    assert report["submission"]["denominator"] == 1
    assert '"students"' not in teacher_payload
    assert "student-1" not in teacher_payload
    assert '"answer":' not in teacher_payload
