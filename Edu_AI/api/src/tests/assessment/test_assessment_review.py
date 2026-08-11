from __future__ import annotations

from test_assessment_attempt_service import _answers, _service
from test_assessment_authoring_api import AuthoringApiFactory, _create_task


def _pending_attempt(service, task):
    attempt = service.start_attempt(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    service.save_answers(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        answers=_answers(4),
        expected_revision=0,
    )
    return service.submit_attempt(
        attempt_id=attempt.attempt_id,
        student_id="student-1",
        idempotency_key="subjective-review-submit",
    )


def test_teacher_review_is_append_only_and_recomputes_verified_best_score(tmp_path):
    service, task = _service(tmp_path, subjective=True)
    pending = _pending_attempt(service, task)
    assert pending.status == "pending_review"
    assert pending.final_score is None

    reviewed = service.finalize_review(
        course_id="course-1",
        task_id=task.task_id,
        attempt_id=pending.attempt_id,
        item_scores={"asi-4": 20},
        reason_code="RUBRIC_CONFIRMED",
        student_comment="说明完整，边界条件可以更清晰。",
        private_comment="Checked against rubric v1.",
        teacher_id="teacher-1",
    )

    assert reviewed.status == "graded"
    assert reviewed.final_score == 95
    assert reviewed.result == "mastered"
    first_audit = service.list_reviews(
        course_id="course-1",
        task_id=task.task_id,
        attempt_id=pending.attempt_id,
        teacher_id="teacher-1",
    )
    assert len(first_audit) == 1
    assert first_audit[0].previous_score is None
    assert first_audit[0].new_score == 20

    adjusted = service.finalize_review(
        course_id="course-1",
        task_id=task.task_id,
        attempt_id=pending.attempt_id,
        item_scores={"asi-4": 0},
        reason_code="RUBRIC_ADJUSTED",
        student_comment="复核后调整该题得分。",
        private_comment="Second-reader adjustment.",
        teacher_id="teacher-1",
    )

    assert adjusted.final_score == 75
    assert adjusted.result == "passed"
    audits = service.list_reviews(
        course_id="course-1",
        task_id=task.task_id,
        attempt_id=pending.attempt_id,
        teacher_id="teacher-1",
    )
    assert [(item.previous_score, item.new_score) for item in audits] == [(None, 20), (20, 0)]
    assignment = service.get_student_assignment(
        course_id="course-1", task_id=task.task_id, student_id="student-1"
    )
    assert assignment.best_final_score == 75
    assert assignment.result == "passed"
    progress = service.learning_service.store.get_progress(task.task_id, "student-1")
    assert progress.completion_basis == "assessment_verified"


def test_review_rejects_missing_or_out_of_range_subjective_scores(tmp_path):
    service, task = _service(tmp_path, subjective=True)
    pending = _pending_attempt(service, task)

    for scores in ({}, {"asi-4": 26}, {"asi-unknown": 10}):
        try:
            service.finalize_review(
                course_id="course-1",
                task_id=task.task_id,
                attempt_id=pending.attempt_id,
                item_scores=scores,
                reason_code="RUBRIC_CONFIRMED",
                student_comment="",
                private_comment="",
                teacher_id="teacher-1",
            )
        except Exception as error:
            assert getattr(error, "code", "") in {
                "REVIEW_SCORE_REQUIRED",
                "INVALID_REVIEW_SCORE",
                "INVALID_REVIEW_ITEM",
            }
        else:
            raise AssertionError("invalid review payload must fail")


def test_teacher_review_api_is_forbidden_to_students_and_returns_visible_feedback(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    teacher = factory.client("teacher-1", "teacher")
    student = factory.client("student-1", "student")
    task = _create_task(teacher)
    path = f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment"
    draft = teacher.post(f"{path}/detect").json()
    subjective = {
        **draft["items"][0],
        "item_type": "short_answer",
        "scoring_key": {},
        "rubric": {"criteria": ["Correct concept and explanation"]},
        "grading_provider": "rubric_ai_teacher",
    }
    updated = teacher.put(f"{path}/draft", json={
        "expected_revision": draft["draft_revision"],
        "pass_threshold": draft["pass_threshold"],
        "mastery_threshold": draft["mastery_threshold"],
        "max_attempts": draft["max_attempts"],
        "assessment_mode": draft["assessment_mode"],
        "answer_reveal_policy": draft["answer_reveal_policy"],
        "shuffle_questions": draft["shuffle_questions"],
        "shuffle_options": draft["shuffle_options"],
        "items": [subjective],
    })
    assert updated.status_code == 200
    assert teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish",
        json={"expected_revision": updated.json()["draft_revision"]},
    ).status_code == 200
    item = student.get(path).json()["items"][0]
    attempt = student.post(f"{path}/attempts").json()
    student.put(f"{path}/attempts/{attempt['attempt_id']}/answers", json={
        "expected_revision": 0,
        "answers": {item["assessment_item_id"]: {"text": "for iterates over an iterable"}},
    })
    pending = student.post(f"{path}/attempts/{attempt['attempt_id']}/submit", json={
        "idempotency_key": "subjective-api-submit",
    })
    assert pending.json()["status"] == "pending_review"
    payload = {
        "item_scores": {item["assessment_item_id"]: item["max_score"]},
        "reason_code": "RUBRIC_CONFIRMED",
        "student_comment": "概念准确。",
        "private_comment": "Teacher checked rubric.",
    }
    assert student.post(f"{path}/attempts/{attempt['attempt_id']}/review", json=payload).status_code == 403
    reviewed = teacher.post(f"{path}/attempts/{attempt['attempt_id']}/review", json=payload)
    assert reviewed.status_code == 200
    assert reviewed.json()["result"] == "mastered"
    audits = teacher.get(f"{path}/attempts/{attempt['attempt_id']}/reviews")
    assert audits.status_code == 200
    assert audits.json()[0]["comment_private"] == "Teacher checked rubric."
    feedback = student.get(f"{path}/feedback").json()
    assert feedback["items"][0]["student_comment"] == "概念准确。"
    assert "comment_private" not in str(feedback)
