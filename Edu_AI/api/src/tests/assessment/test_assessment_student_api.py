from __future__ import annotations

import json

from test_assessment_authoring_api import AuthoringApiFactory, _create_task


def _published(factory: AuthoringApiFactory):
    teacher = factory.client("teacher-1", "teacher")
    task = _create_task(teacher)
    draft = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment/detect"
    ).json()
    published = teacher.post(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/publish",
        json={"expected_revision": draft["draft_revision"]},
    )
    assert published.status_code == 200
    return task


def test_student_projection_never_contains_private_scoring_fields(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    task = _published(factory)
    student = factory.client("student-1", "student")

    response = student.get(
        f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment"
    )

    assert response.status_code == 200
    serialized = json.dumps(response.json(), ensure_ascii=False)
    assert "scoring_key" not in serialized
    assert "correct_option_id" not in serialized
    assert "explanation" not in serialized
    assert response.json()["items"][0]["prompt"]["stem"]


def test_student_attempt_round_trip_uses_trusted_score_outcome(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    task = _published(factory)
    student = factory.client("student-1", "student")
    path = f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment"
    item = student.get(path).json()["items"][0]
    attempt = student.post(f"{path}/attempts").json()

    saved = student.put(
        f"{path}/attempts/{attempt['attempt_id']}/answers",
        json={
            "expected_revision": 0,
            "answers": {
                item["assessment_item_id"]: {"selected_option_id": "opt-1"}
            },
        },
    )
    assert saved.status_code == 200
    submitted = student.post(
        f"{path}/attempts/{attempt['attempt_id']}/submit",
        json={"idempotency_key": "student-submit-1"},
    )

    assert submitted.status_code == 200
    assert submitted.json()["final_score"] == 100
    assert submitted.json()["result"] == "mastered"
    history = student.get(f"{path}/attempts")
    assert history.status_code == 200
    assert [item["final_score"] for item in history.json()] == [100]
    task_view = student.get("/api/courses/course-1/learning/tasks").json()[0]
    assert task_view["my_progress"]["completion_basis"] == "assessment_verified"


def test_attempt_route_rejects_cross_task_and_unknown_item_ids(tmp_path):
    factory = AuthoringApiFactory(tmp_path)
    task = _published(factory)
    student = factory.client("student-1", "student")
    path = f"/api/courses/course-1/learning/tasks/{task['task_id']}/assessment"
    attempt = student.post(f"{path}/attempts").json()

    cross_task = student.put(
        f"/api/courses/course-1/learning/tasks/another-task/assessment/attempts/{attempt['attempt_id']}/answers",
        json={"expected_revision": 0, "answers": {}},
    )
    unknown_item = student.put(
        f"{path}/attempts/{attempt['attempt_id']}/answers",
        json={"expected_revision": 0, "answers": {"asi-unknown": {"text": "x"}}},
    )

    assert cross_task.status_code == 404
    assert unknown_item.status_code == 422
    assert unknown_item.json()["detail"]["code"] == "INVALID_ANSWER_ITEM"
