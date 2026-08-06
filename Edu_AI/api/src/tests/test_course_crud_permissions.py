from __future__ import annotations

import pytest

from course_api_test_support import CourseApiTestFactory, course_update_payload


@pytest.fixture
def course_api(tmp_path, monkeypatch):
    return CourseApiTestFactory(tmp_path, monkeypatch)


def test_course_list_requires_auth_and_returns_membership_role(course_api):
    anonymous = course_api.anonymous().get("/api/courses")
    response = course_api.client_for("teacher-a", "teacher").get(
        "/api/courses"
    )

    assert anonymous.status_code == 401
    assert response.status_code == 200
    assert response.json()[0]["membership_role"] == "editor"


def test_stale_course_revision_returns_409(course_api):
    client = course_api.client_for("teacher-a", "teacher")
    course = client.get("/api/courses/course-1").json()

    first = client.put(
        "/api/courses/course-1",
        json=course_update_payload(course, title="First"),
    )
    stale = client.put(
        "/api/courses/course-1",
        json=course_update_payload(course, title="Stale"),
    )

    assert first.status_code == 200
    assert first.json()["revision"] == course["revision"] + 1
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "COURSE_REVISION_CONFLICT"


def test_viewer_cannot_update_course(course_api):
    viewer = course_api.client_for("student-a", "student")
    course = viewer.get("/api/courses/course-1").json()

    response = viewer.put(
        "/api/courses/course-1",
        json=course_update_payload(course, title="Forbidden"),
    )

    assert response.status_code == 403


def test_new_course_owner_and_development_memberships_are_created(course_api):
    client = course_api.client_for("teacher-a", "teacher")
    response = client.post(
        "/api/courses",
        json={
            "id": "course-2",
            "title": "Course two",
            "description": "New shared course",
            "icon": "BookOutlined",
            "color": "#3157d5",
            "objectives": [],
            "knowledgeGraph": "",
        },
    )

    assert response.status_code == 200
    assert course_api.memberships.get("course-2", "teacher-a").role == "owner"
    assert course_api.memberships.get("course-2", "teacher-b").role == "editor"
    assert course_api.memberships.get("course-2", "student-a").role == "viewer"
