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
        def get_latest_graph_version(self, library_id):
            assert library_id == "course-1"
            return {"version": 7, "graph": _valid_small_graph()}

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
    assert body["config"]["prefer_complete_textbooks"] is True
    assert body["config"]["max_online_textbooks"] == 2
    assert body["config"]["max_search_rounds_per_leaf"] == 2
    assert body["config"]["update_strategy"] == "incremental"
    assert body["baseline_graph_version"] == 7
    assert body["baseline_graph"] == _valid_small_graph()
    assert body["current_graph_summary"]["node_count"] == 13
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_online_textbooks", 6),
        ("max_search_rounds_per_leaf", 4),
    ],
)
def test_build_config_rejects_textbook_first_limits(course_api, field, value):
    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds",
        json={"config": {field: value}},
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


def _valid_small_graph():
    return {
        "id": "course-root",
        "label": "Course one",
        "data": {"type": "course", "summary": "课程知识结构"},
        "children": [
            {
                "id": f"module-{module_index}",
                "label": f"主题模块 {module_index}",
                "data": {"type": "knowledge_module", "summary": "模块说明"},
                "children": [
                    {
                        "id": f"point-{module_index}-{point_index}",
                        "label": f"具体知识点 {module_index}-{point_index}",
                        "data": {"type": "knowledge_point", "summary": "知识点说明"},
                        "children": [],
                    }
                    for point_index in range(1, 4)
                ],
            }
            for module_index in range(1, 4)
        ],
    }


def test_graph_save_validates_and_persists_editor_identity(course_api, monkeypatch):
    from app.api import courses

    captured = {}

    class Repository:
        def get_build(self, build_id):
            return {
                "build_id": build_id,
                "library_id": "course-1",
                "status": "draft",
                "revision": 2,
                "config": {
                    "graph_depth": 3,
                    "target_module_count": 3,
                    "target_points_per_module": 3,
                },
                "textbooks": [],
            }

        def update_build_draft(self, build_id, *, expected_revision, changes, phase):
            captured.update(
                build_id=build_id,
                expected_revision=expected_revision,
                changes=changes,
                phase=phase,
            )
            return {
                **self.get_build(build_id),
                "revision": expected_revision + 1,
                "phase": phase,
                **changes,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())

    response = course_api.client_for("teacher-a", "teacher").put(
        "/api/courses/course-1/knowledge-builds/kb-1/graph",
        json={"expected_revision": 2, "root": _valid_small_graph()},
    )

    assert response.status_code == 200
    assert captured["phase"] == "graph_review"
    graph = captured["changes"]["graph_draft"]
    assert graph["data"]["edited_by"] == "teacher-a"
    assert graph["data"]["validation"]["status"] == "passed"
    assert graph["data"]["validation"]["leaf_count"] == 9


def test_graph_save_rejects_invalid_structure_without_persisting(course_api, monkeypatch):
    from app.api import courses

    class Repository:
        def get_build(self, build_id):
            return {
                "build_id": build_id,
                "library_id": "course-1",
                "status": "draft",
                "revision": 2,
                "config": {
                    "graph_depth": 3,
                    "target_module_count": 3,
                    "target_points_per_module": 3,
                },
                "textbooks": [],
            }

        def update_build_draft(self, *_args, **_kwargs):
            pytest.fail("invalid graph must not be persisted")

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())
    invalid = _valid_small_graph()
    invalid["children"][0]["children"][0]["label"] = ""

    response = course_api.client_for("teacher-a", "teacher").put(
        "/api/courses/course-1/knowledge-builds/kb-1/graph",
        json={"expected_revision": 2, "root": invalid},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "GRAPH_SCHEMA_INVALID"
    assert any(issue["code"] == "EMPTY_LABEL" for issue in detail["issues"])


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


def test_blocked_build_can_retry_from_stable_checkpoint(course_api, monkeypatch):
    from app.api import courses

    captured = {}

    class Repository:
        def get_build(self, build_id):
            return {
                "build_id": build_id,
                "library_id": "course-1",
                "status": "blocked",
                "revision": 4,
                "graph_confirmed_at": "2026-08-12T10:00:00+00:00",
                "confirmed_graph_revision": 4,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())

    def submit(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "edu_job_id": "job-retry-1",
                "kind": "build_knowledge_index",
                "status": "queued",
            }
        )

    monkeypatch.setattr(courses, "submit_course_knowledge_plan_build_job", submit)
    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds/kb-1/retry"
    )

    assert response.status_code == 202
    assert captured == {
        "course_id": "course-1",
        "owner_user_id": "teacher-a",
        "build_id": "kb-1",
        "retry": True,
    }
