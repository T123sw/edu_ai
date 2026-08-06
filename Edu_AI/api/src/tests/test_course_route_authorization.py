from __future__ import annotations

import pytest

from course_api_test_support import CourseApiTestFactory


@pytest.fixture
def course_api(tmp_path, monkeypatch):
    return CourseApiTestFactory(tmp_path, monkeypatch)


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "put",
            "/api/courses/course-1/knowledge-graph",
            {
                "root": {
                    "id": "root",
                    "label": "Course",
                    "data": {"level": 0},
                    "children": [],
                }
            },
        ),
        (
            "post",
            "/api/courses/course-1/knowledge-graph/allocate-hours",
            {"total_hours": 16},
        ),
        (
            "post",
            "/api/courses/course-1/knowledge-base/documents/missing/reindex",
            None,
        ),
        (
            "delete",
            "/api/courses/course-1/knowledge-base/documents/missing",
            None,
        ),
        (
            "post",
            "/api/courses/course-1/classrooms/generate",
            {"requirement": "Explain the course"},
        ),
    ],
)
def test_viewer_cannot_mutate_course_content(
    course_api, method, path, payload
):
    viewer = course_api.client_for("student-a", "student")

    response = viewer.request(method.upper(), path, json=payload)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/courses/course-1/knowledge-base/documents",
        "/api/courses/course-1/knowledge-graph",
        "/api/courses/course-1/classrooms",
    ],
)
def test_anonymous_course_content_reads_require_authentication(course_api, path):
    response = course_api.anonymous().get(path)

    assert response.status_code == 401
