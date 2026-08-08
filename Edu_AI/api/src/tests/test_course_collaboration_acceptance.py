from __future__ import annotations

import pytest

from course_api_test_support import CourseApiTestFactory, course_update_payload


@pytest.fixture
def course_api(tmp_path, monkeypatch):
    return CourseApiTestFactory(tmp_path, monkeypatch)


def test_two_teachers_share_course_and_student_is_read_only(course_api):
    teacher_a = course_api.client_for("teacher-a", "teacher")
    teacher_b = course_api.client_for("teacher-b", "teacher")
    student = course_api.client_for("student-a", "student")

    course = teacher_a.get("/api/courses/course-1").json()
    updated = teacher_a.put(
        "/api/courses/course-1",
        json=course_update_payload(course, title="Shared title"),
    )

    assert updated.status_code == 200
    assert teacher_b.get("/api/courses/course-1").json()["title"] == "Shared title"
    assert student.get("/api/courses/course-1").json()["title"] == "Shared title"
    denied = student.put(
        "/api/courses/course-1",
        json=course_update_payload(updated.json(), title="Forbidden edit"),
    )
    assert denied.status_code == 403


def test_teacher_b_reads_and_manages_teacher_a_course_material(course_api):
    assert course_api.manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Teacher A report"},
        owner_user_id="teacher-a",
        visibility="course",
    )
    teacher_b = course_api.client_for("teacher-b", "teacher")
    student = course_api.client_for("student-a", "student")

    detail = teacher_b.get(
        "/api/courses/course-1/materials/report/report-1"
    )
    renamed = teacher_b.patch(
        "/api/courses/course-1/materials/report/report-1",
        json={"title": "Shared report"},
    )
    denied = student.delete(
        "/api/courses/course-1/materials/report/report-1"
    )

    assert detail.status_code == 200
    assert detail.json()["created_by"] == "teacher-a"
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Shared report"
    assert denied.status_code == 403
