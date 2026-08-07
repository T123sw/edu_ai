import asyncio

import pytest

from app.api import teacher as teacher_api
from app.services import teacher_service
from core import course_storage
from core.course_storage import CourseStorageManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    instance = CourseStorageManager(root_path=str(tmp_path))
    instance.create_course_structure("course-1")
    monkeypatch.setattr(course_storage, "CourseStorageManager", lambda: instance)
    return instance


@pytest.mark.parametrize(
    ("material_type", "delete_material"),
    [
        ("report", teacher_service.delete_report),
        ("quiz", teacher_service.delete_quiz),
    ],
)
def test_legacy_teacher_delete_requires_private_material_owner(
    manager, material_type, delete_material
):
    assert manager.save_generated_material(
        "course-1",
        material_type,
        "private-a",
        {"title": "Owner-only resource"},
        owner_user_id="teacher-a",
    )

    with pytest.raises(KeyError):
        delete_material("private-a", "course-1", owner_user_id="teacher-b")

    assert manager.get_generated_material(
        "course-1", material_type, "private-a", owner_user_id="teacher-a"
    ) is not None
    delete_material("private-a", "course-1", owner_user_id="teacher-a")
    assert manager.get_generated_material(
        "course-1", material_type, "private-a", owner_user_id="teacher-a"
    ) is None


def test_legacy_lesson_plan_delete_checks_course_owner_before_local_delete(
    manager, monkeypatch
):
    local_deletes: list[str] = []
    monkeypatch.setattr(
        teacher_service.lesson_plan_storage,
        "delete_plan",
        lambda plan_id: local_deletes.append(plan_id),
    )
    assert manager.save_generated_material(
        "course-1",
        "lesson_plan",
        "private-a",
        {"title": "Owner-only lesson plan"},
        owner_user_id="teacher-a",
    )

    with pytest.raises(KeyError):
        teacher_service.delete_lesson_plan(
            "private-a", "course-1", owner_user_id="teacher-b"
        )

    assert local_deletes == []
    teacher_service.delete_lesson_plan(
        "private-a", "course-1", owner_user_id="teacher-a"
    )
    assert local_deletes == ["private-a"]
    assert manager.get_generated_material(
        "course-1", "lesson_plan", "private-a", owner_user_id="teacher-a"
    ) is None


@pytest.mark.parametrize(
    ("endpoint_name", "service_alias"),
    [
        ("delete_lesson_plan_endpoint", "_svc_delete_lesson_plan"),
        ("delete_report_endpoint", "_svc_delete_report"),
        ("delete_quiz_endpoint", "_svc_delete_quiz"),
    ],
)
def test_legacy_delete_endpoints_forward_authenticated_username(
    monkeypatch, endpoint_name, service_alias
):
    calls: list[tuple[str, str, str]] = []

    def fake_delete(material_id, course_id, *, owner_user_id):
        calls.append((material_id, course_id, owner_user_id))

    monkeypatch.setattr(teacher_api, service_alias, fake_delete)
    endpoint = getattr(teacher_api, endpoint_name)

    result = asyncio.run(
        endpoint(
            "private-a",
            course_id="course-1",
            current_user={"username": "teacher-b", "role": "teacher"},
        )
    )

    assert calls == [("private-a", "course-1", "teacher-b")]
    assert "message" in result
