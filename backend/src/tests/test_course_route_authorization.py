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


def test_viewer_only_sees_published_documents_and_generation_provenance(course_api):
    course_api.manager.save_knowledge_base_index(
        "course-1",
        [
            {
                "id": "ready-generated",
                "filename": "AI 补充资料.md",
                "status": "ready",
                "source_type": "model_generated",
                "generation_review_score": 92,
                "generation_audit": {"reviewed": True},
            },
            {
                "id": "staged-generated",
                "filename": "尚未发布.md",
                "status": "received",
                "source_type": "model_generated",
                "generation_review_score": 95,
            },
        ],
    )

    viewer = course_api.client_for("student-a", "student")
    response = viewer.get("/api/courses/course-1/knowledge-base/documents")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["ready-generated"]
    assert response.json()[0]["source_type"] == "model_generated"
    assert response.json()[0]["generation_review_score"] == 92
    assert response.json()[0]["generation_audit"] == {"reviewed": True}
