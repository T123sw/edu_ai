from __future__ import annotations

import pytest

from course_api_test_support import CourseApiTestFactory


@pytest.fixture
def course_api(tmp_path, monkeypatch):
    return CourseApiTestFactory(tmp_path, monkeypatch)


def _new_course_payload() -> dict:
    return {
        "title": "Python 控制流程入门",
        "description": "学习条件判断与循环控制",
        "icon": "BookOutlined",
        "color": "#3157d5",
        "objectives": ["条件判断", "循环控制"],
        "language": "zh-CN",
    }


def test_teacher_creates_private_course_with_unique_join_code(course_api) -> None:
    teacher = course_api.client_for("teacher-a", "teacher")
    student = course_api.client_for("student-a", "student")

    created = teacher.post("/api/courses", json=_new_course_payload())

    assert created.status_code == 200
    body = created.json()
    assert body["membership_role"] == "owner"
    assert len(body["course_code"]) == 8
    assert body["course_code"].isalnum()
    assert course_api.memberships.get(body["id"], "teacher-a").role == "owner"
    assert course_api.memberships.get(body["id"], "student-a") is None
    assert student.get(f"/api/courses/{body['id']}").status_code == 403


def test_student_joins_by_code_and_code_is_hidden_after_join(course_api) -> None:
    teacher = course_api.client_for("teacher-a", "teacher")
    student = course_api.client_for("student-a", "student")
    created = teacher.post("/api/courses", json=_new_course_payload()).json()

    joined = student.post(
        "/api/courses/join",
        json={"course_code": created["course_code"].lower()},
    )

    assert joined.status_code == 200
    assert joined.json()["id"] == created["id"]
    assert joined.json()["membership_role"] == "viewer"
    assert joined.json()["course_code"] is None
    assert course_api.memberships.get(created["id"], "student-a").role == "viewer"


def test_only_students_can_self_join(course_api) -> None:
    owner = course_api.client_for("teacher-a", "teacher")
    teacher = course_api.client_for("teacher-b", "teacher")
    created = owner.post("/api/courses", json=_new_course_payload()).json()

    response = teacher.post(
        "/api/courses/join",
        json={"course_code": created["course_code"]},
    )

    assert response.status_code == 403


def test_owner_manages_members_without_removing_last_owner(course_api) -> None:
    owner = course_api.client_for("teacher-a", "teacher")
    created = owner.post("/api/courses", json=_new_course_payload()).json()
    course_id = created["id"]

    added = owner.post(
        f"/api/courses/{course_id}/members",
        json={"user_id": "teacher-b", "role": "editor"},
    )
    members = owner.get(f"/api/courses/{course_id}/members")
    protected = owner.delete(f"/api/courses/{course_id}/members/teacher-a")
    removed = owner.delete(f"/api/courses/{course_id}/members/teacher-b")

    assert added.status_code == 200, added.text
    assert added.json()["role"] == "editor"
    assert members.status_code == 200
    assert {item["user_id"] for item in members.json()["items"]} == {
        "teacher-a",
        "teacher-b",
    }
    assert protected.status_code == 409
    assert removed.status_code == 200


def test_non_owner_cannot_manage_members(course_api) -> None:
    course_api.memberships.upsert("course-1", "teacher-a", "owner", added_by="fixture")
    editor = course_api.client_for("teacher-b", "teacher")

    assert editor.get("/api/courses/course-1/members").status_code == 403


def test_student_can_leave_own_course_and_teacher_cannot_use_student_exit(course_api) -> None:
    student = course_api.client_for("student-a", "student")
    teacher = course_api.client_for("teacher-a", "teacher")

    left = student.delete("/api/courses/course-1/membership")
    denied = teacher.delete("/api/courses/course-1/membership")

    assert left.status_code == 200
    assert course_api.memberships.get("course-1", "student-a") is None
    assert denied.status_code == 403
    assert course_api.memberships.get("course-1", "teacher-a") is not None


def test_student_cannot_leave_course_twice(course_api) -> None:
    student = course_api.client_for("student-a", "student")

    assert student.delete("/api/courses/course-1/membership").status_code == 200
    second = student.delete("/api/courses/course-1/membership")

    assert second.status_code == 404
    assert second.json()["detail"]["code"] == "MEMBER_NOT_FOUND"
