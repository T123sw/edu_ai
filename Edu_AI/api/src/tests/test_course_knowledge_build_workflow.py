from __future__ import annotations

import pytest
from types import SimpleNamespace

from course_api_test_support import CourseApiTestFactory


@pytest.fixture
def course_api(tmp_path, monkeypatch):
    return CourseApiTestFactory(tmp_path, monkeypatch)


def test_create_build_draft_normalizes_config_without_searching(course_api, monkeypatch):
    from app.api import courses

    captured = {}

    class Repository:
        def create_build_draft(self, *, course_id, triggered_by, plan):
            captured.update(
                course_id=course_id,
                triggered_by=triggered_by,
                plan=plan,
            )
            return {
                "build_id": "kb-draft-1",
                "library_id": course_id,
                "status": "draft",
                "phase": "draft_config",
                "revision": 1,
                "graph_confirmed_at": None,
                "confirmed_graph_revision": None,
                "confirmed_by": None,
                **plan,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())
    assert not hasattr(courses, "search_web_sources")

    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds",
        json={
            "config": {
                "preset": "small",
                "minimum_web_materials_per_leaf": 0,
            }
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["phase"] == "draft_config"
    assert body["config"]["target_module_count"] == 3
    assert body["config"]["target_points_per_module"] == 3
    assert body["config"]["minimum_web_materials_per_leaf"] == 0
    assert body["graph_draft"] is None
    assert captured["course_id"] == "course-1"
    assert captured["plan"]["course_snapshot"]["title"] == "Course one"


def test_build_config_rejects_invalid_ai_and_material_limits(course_api):
    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds",
        json={
            "config": {
                "target_materials_per_leaf": 2,
                "minimum_web_materials_per_leaf": 3,
            }
        },
    )

    assert response.status_code == 422


def test_unconfirmed_build_cannot_start_formal_job(course_api, monkeypatch):
    from app.api import courses

    class Repository:
        def get_build(self, build_id):
            assert build_id == "kb-unconfirmed"
            return {
                "build_id": build_id,
                "library_id": "course-1",
                "status": "draft",
                "phase": "graph_review",
                "revision": 3,
                "graph_confirmed_at": None,
                "confirmed_graph_revision": None,
                "confirmed_by": None,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())
    monkeypatch.setattr(
        courses,
        "submit_course_knowledge_plan_build_job",
        lambda **_kwargs: pytest.fail("unconfirmed build must not create a job"),
    )

    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds/kb-unconfirmed/start"
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "GRAPH_CONFIRMATION_REQUIRED"


def test_viewer_cannot_create_build_draft(course_api):
    response = course_api.client_for("student-a", "student").post(
        "/api/courses/course-1/knowledge-builds",
        json={},
    )

    assert response.status_code == 403


def test_generate_graph_endpoint_queues_model_job_with_revision(course_api, monkeypatch):
    from app.api import courses

    captured = {}

    class Repository:
        def get_build(self, build_id):
            return {
                "build_id": build_id,
                "library_id": "course-1",
                "status": "draft",
                "revision": 2,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())

    def submit(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "edu_job_id": "job-graph-1",
                "kind": "generate_graph",
                "status": "queued",
            }
        )

    monkeypatch.setattr(courses, "submit_course_knowledge_graph_generation_job", submit)

    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds/kb-1/graph/generate",
        json={"expected_revision": 2, "target_module_id": "module-poetry"},
    )

    assert response.status_code == 202
    assert response.json()["kind"] == "generate_graph"
    assert captured == {
        "course_id": "course-1",
        "owner_user_id": "teacher-a",
        "build_id": "kb-1",
        "expected_revision": 2,
        "target_module_id": "module-poetry",
    }


def test_textbook_upload_is_scoped_to_build_draft(course_api, monkeypatch):
    from app.api import courses

    captured = {}

    class Repository:
        def get_build(self, build_id):
            return {
                "build_id": build_id,
                "library_id": "course-1",
                "status": "draft",
                "revision": 1,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())

    def stage(**kwargs):
        captured.update(kwargs)
        textbook = {
            "textbook_id": "textbook-1",
            "filename": kwargs["filename"],
            "status": "queued",
        }
        return (
            {
                "build_id": "kb-1",
                "library_id": "course-1",
                "status": "draft",
                "phase": "textbook_parsing",
                "revision": 2,
                "textbooks": [textbook],
            },
            textbook,
        )

    monkeypatch.setattr(courses, "stage_course_knowledge_textbook", stage)
    monkeypatch.setattr(
        courses,
        "submit_course_knowledge_textbook_parse_job",
        lambda **_kwargs: SimpleNamespace(
            model_dump=lambda **_options: {
                "edu_job_id": "job-parse-1",
                "kind": "parse_document",
                "status": "queued",
            }
        ),
    )

    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds/kb-1/textbooks",
        data={"expected_revision": "1"},
        files={"file": ("教材.md", "# 目录".encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 202
    assert response.json()["textbook"]["status"] == "queued"
    assert response.json()["job"]["kind"] == "parse_document"
    assert captured["build_id"] == "kb-1"
    assert captured["file_bytes"] == "# 目录".encode("utf-8")
