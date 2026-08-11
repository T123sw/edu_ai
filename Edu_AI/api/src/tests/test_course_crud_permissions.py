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


def test_postgres_course_list_does_not_require_a_local_asset_directory(
    course_api, monkeypatch
):
    database_only = {
        "id": "database-only-course",
        "title": "Database only",
        "description": "No local asset directory yet",
        "icon": "menu_book",
        "color": "#3157d5",
        "objectives": [],
        "revision": 0,
    }

    class Repository:
        def list(self):
            return [database_only]

    monkeypatch.setattr(course_api.manager, "_course_uses_postgres", lambda: True)
    monkeypatch.setattr(course_api.manager, "_course_repository", Repository)
    course_api.memberships.upsert(
        "database-only-course", "teacher-a", "owner", added_by="fixture"
    )

    response = course_api.client_for("teacher-a", "teacher").get("/api/courses")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["database-only-course"]


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


def test_new_course_is_private_to_creator_until_members_are_added(course_api):
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
    assert course_api.memberships.get("course-2", "teacher-b") is None
    assert course_api.memberships.get("course-2", "student-a") is None


def test_new_course_can_use_server_generated_id_and_preserves_planning_metadata(course_api):
    client = course_api.client_for("teacher-a", "teacher")

    response = client.post(
        "/api/courses",
        json={
            "title": "Linear algebra",
            "description": "Vectors and matrices for engineering",
            "icon": "menu_book",
            "color": "#3157d5",
            "objectives": ["Understand vector spaces"],
            "audience": "First-year undergraduates",
            "language": "en",
            "difficulty": "intermediate",
            "knowledgeGraph": "",
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["id"].startswith("course-")
    assert created["audience"] == "First-year undergraduates"
    assert created["language"] == "en"
    assert created["difficulty"] == "intermediate"
    assert course_api.memberships.get(created["id"], "teacher-a").role == "owner"


def test_student_cannot_create_course_and_unsafe_explicit_id_is_rejected(course_api):
    payload = {
        "id": "../escape",
        "title": "Unsafe",
        "description": "Unsafe",
        "icon": "menu_book",
        "color": "#3157d5",
        "objectives": [],
        "knowledgeGraph": "",
    }

    assert course_api.client_for("teacher-a", "teacher").post("/api/courses", json=payload).status_code == 422
    payload["id"] = "student-course"
    assert course_api.client_for("student-a", "student").post("/api/courses", json=payload).status_code == 403


def test_legacy_preview_only_creates_draft_and_student_is_denied(course_api, monkeypatch):
    from app.api import courses

    class Repository:
        def create_build_draft(self, *, course_id, triggered_by, plan):
            return {
                "build_id": "kb-1",
                "library_id": course_id,
                "status": "draft",
                "phase": "draft_config",
                "revision": 1,
                **plan,
            }

    monkeypatch.setattr(courses, "get_postgres_knowledge_repository", lambda: Repository())
    teacher_response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses/course-1/knowledge-builds/preview",
        json={"discover_sources": False, "max_results_per_topic": 4},
    )
    student_response = course_api.client_for("student-a", "student").post(
        "/api/courses/course-1/knowledge-builds/preview",
        json={"discover_sources": False},
    )

    assert teacher_response.status_code == 201
    body = teacher_response.json()
    assert body["build_id"] == "kb-1"
    assert body["course_snapshot"]["title"] == "Course one"
    assert body["topics"] == []
    assert body["graph_draft"] is None
    assert body["source_candidates"] == []
    assert body["deprecation"]["deprecated"] is True
    assert student_response.status_code == 403


def test_shared_material_is_readable_by_editor_but_viewer_cannot_delete(course_api):
    assert course_api.manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Shared report"},
        owner_user_id="teacher-a",
        visibility="course",
    )
    editor = course_api.client_for("teacher-b", "teacher")
    viewer = course_api.client_for("student-a", "student")

    detail = editor.get("/api/courses/course-1/materials/report/report-1")
    denied = viewer.delete(
        "/api/courses/course-1/materials/report/report-1"
    )

    assert detail.status_code == 200
    assert detail.json()["created_by"] == "teacher-a"
    assert denied.status_code == 403
