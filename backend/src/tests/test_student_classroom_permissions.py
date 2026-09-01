from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import courses
from course_api_test_support import CourseApiTestFactory


@pytest.fixture()
def course_api(tmp_path, monkeypatch):
    factory = CourseApiTestFactory(tmp_path, monkeypatch)
    factory.users.append({"username": "student-b", "role": "student"})
    factory.memberships.upsert(
        "course-1", "student-b", "viewer", added_by="fixture"
    )
    return factory


def test_student_viewer_can_generate_a_private_personal_classroom(
    course_api,
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        courses,
        "build_default_generation_source_resolver",
        lambda _manager: SimpleNamespace(validate=lambda *_args, **_kwargs: ()),
        raising=False,
    )

    async def submit(**kwargs):
        captured.update(kwargs)
        return {"edu_job_id": "student-classroom-job", "status": "queued"}

    monkeypatch.setattr(courses, "submit_classroom_generation_job", submit)
    student = course_api.client_for("student-a", "student")

    response = student.post(
        "/api/courses/course-1/classrooms/generate",
        json={
            "requirement": "解释函数",
            "source_mode": "none",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 202
    assert response.json()["edu_job_id"] == "student-classroom-job"
    assert captured["owner"] == "student-a"
    assert captured["course_id"] == "course-1"


def test_classroom_spaces_separate_owner_private_items_and_course_snapshots(
    course_api,
):
    manager = course_api.manager
    assert manager.save_generated_material(
        "course-1",
        "classroom",
        "student-a-private",
        {"title": "A private"},
        owner_user_id="student-a",
        visibility="private",
    )
    assert manager.save_generated_material(
        "course-1",
        "classroom",
        "student-b-private",
        {"title": "B private"},
        owner_user_id="student-b",
        visibility="private",
    )
    manager.save_published_material_manifest(
        "course-1",
        "classroom",
        "teacher-shared",
        {"title": "Published classroom"},
    )
    student = course_api.client_for("student-a", "student")

    mine = student.get("/api/courses/course-1/classrooms?space=mine")
    shared = student.get("/api/courses/course-1/classrooms?space=course")
    unsupported = student.get("/api/courses/course-1/classrooms?space=all")

    assert mine.status_code == 200
    assert [item["material_id"] for item in mine.json()] == [
        "student-a-private"
    ]
    assert shared.status_code == 200
    assert [item["material_id"] for item in shared.json()] == [
        "teacher-shared"
    ]
    assert unsupported.status_code == 422


def test_student_cannot_load_or_export_another_students_private_classroom(
    course_api,
    monkeypatch,
):
    assert course_api.manager.save_generated_material(
        "course-1",
        "classroom",
        "student-b-private",
        {"title": "B private"},
        owner_user_id="student-b",
        visibility="private",
    )

    async def must_not_submit(**_kwargs):
        raise AssertionError("another user's classroom must not be exported")

    monkeypatch.setattr(courses, "submit_classroom_video_export_job", must_not_submit)
    student = course_api.client_for("student-a", "student")

    read_response = student.get(
        "/api/courses/course-1/classrooms/student-b-private"
    )
    export_response = student.post(
        "/api/courses/course-1/classrooms/student-b-private/video/export"
    )

    assert read_response.status_code == 404
    assert export_response.status_code == 404


def test_standard_classroom_version_is_pinned_for_students_but_previewable_by_teacher(
    course_api,
    monkeypatch,
):
    class Materials:
        def get(self, course_id, material_type, material_id):
            assert (course_id, material_type, material_id) == (
                "course-1",
                "classroom",
                "classroom-1",
            )
            return {
                "origin_type": "standard",
                "standard_kind": "classroom",
                "approved_version": 2,
            }

        def get_version(self, _course_id, _material_type, _material_id, version):
            return {"title": f"version {version}", "scenes": []} if version in {1, 2} else None

    class Learning:
        def get_manifest(self, _course_id, _resource_id, version):
            return SimpleNamespace(content_hash=f"hash-{version}")

    monkeypatch.setattr(courses, "get_postgres_material_repository", lambda: Materials())
    monkeypatch.setattr(courses, "get_resource_learning_repository", lambda: Learning())
    student = course_api.client_for("student-a", "student")
    teacher = course_api.client_for("teacher-a", "teacher")

    approved = student.get(
        "/api/courses/course-1/classrooms/classroom-1?resource_version=2"
    )
    hidden_old = student.get(
        "/api/courses/course-1/classrooms/classroom-1?resource_version=1"
    )
    teacher_preview = teacher.get(
        "/api/courses/course-1/classrooms/classroom-1?resource_version=1"
    )

    assert approved.status_code == 200
    assert approved.json()["content_hash"] == "hash-2"
    assert hidden_old.status_code == 404
    assert teacher_preview.status_code == 200
    assert teacher_preview.json()["version"] == 1

