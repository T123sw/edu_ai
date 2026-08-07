import pytest

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
