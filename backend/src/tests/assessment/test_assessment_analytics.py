from __future__ import annotations

from test_assessment_attempt_service import _answers, _service
from test_assessment_authoring_api import AuthoringApiFactory, _create_task


def _submit(service, task, student_id: str, correct_count: int):
    attempt = service.start_attempt(
        course_id="course-1", task_id=task.task_id, student_id=student_id
    )
    service.save_answers(
        attempt_id=attempt.attempt_id,
        student_id=student_id,
        answers=_answers(correct_count),
        expected_revision=0,
    )
    return service.submit_attempt(
        attempt_id=attempt.attempt_id,
        student_id=student_id,
        idempotency_key=f"analytics-{student_id}",
    )


def test_teacher_analytics_preserves_denominators_and_actionable_queues(tmp_path):
    service, task = _service(tmp_path)
    memberships = service.learning_service.membership_lookup("course-1")
    memberships.extend([
        {"user_id": "student-2", "role": "viewer"},
        {"user_id": "student-3", "role": "viewer"},
        {"user_id": "student-4", "role": "viewer"},
    ])
    _submit(service, task, "student-1", 2)
    _submit(service, task, "student-3", 0)
    _submit(service, task, "student-4", 4)

    report = service.get_task_analytics(
        course_id="course-1", task_id=task.task_id, teacher_id="teacher-1"
    )

    assert report["enrolled"] == 4
    assert report["participation"] == {"numerator": 3, "denominator": 4, "rate": 0.75}
    assert report["submission"] == {"numerator": 3, "denominator": 4, "rate": 0.75}
    assert report["pass"] == {"numerator": 1, "denominator": 4, "rate": 0.25}
    assert report["mastery"] == {"numerator": 1, "denominator": 4, "rate": 0.25}
    assert report["mean_best_score"] == 50
    assert report["median_best_score"] == 50
    assert report["pending_review"] == 0
    queues = {item["student_id"]: item["status"] for item in report["students"]}
    assert queues == {
        "student-1": "retry_available",
        "student-2": "not_started",
        "student-3": "retry_available",
        "student-4": "mastered",
    }
    assert report["items"][0]["sample_count"] == 3
    assert report["knowledge_points"][0]["knowledge_point_id"] == "loops"


def test_class_analytics_api_is_teacher_only(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")
    task = _create_task(teacher)
    path = f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment"
    draft = teacher.post(f"{path}/detect").json()
    teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish",
        json={"expected_revision": draft["draft_revision"]},
    )

    assert student.get(f"{path}/analytics").status_code == 403
    response = teacher.get(f"{path}/analytics")
    assert response.status_code == 200
    assert response.json()["enrolled"] == 1
    assert response.json()["pass"] == {"numerator": 0, "denominator": 1, "rate": 0.0}
