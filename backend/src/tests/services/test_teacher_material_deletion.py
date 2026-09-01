import asyncio

import pytest

from app.api import teacher as teacher_api
from core.course_storage import CourseStorageManager


@pytest.mark.parametrize(
    "endpoint_name",
    [
        "delete_lesson_plan_endpoint",
        "delete_report_endpoint",
        "delete_quiz_endpoint",
    ],
)
def test_legacy_teacher_delete_endpoints_are_retired(endpoint_name):
    endpoint = getattr(teacher_api, endpoint_name)

    with pytest.raises(teacher_api.HTTPException) as raised:
        asyncio.run(
            endpoint(
                "resource-1",
                course_id="course-1",
                current_user={"username": "teacher-a", "role": "teacher"},
            )
        )

    assert raised.value.status_code == 410
    assert raised.value.detail == {
        "code": "LEGACY_MATERIAL_DELETE_RETIRED",
        "message": "旧删除接口已停用，请使用课程资源删除接口",
        "replacement": "/api/courses/{course_id}/materials/{material_type}/{material_id}",
    }


@pytest.mark.parametrize(
    ("endpoint_name", "material_type"),
    [
        ("delete_lesson_plan_endpoint", "lesson_plan"),
        ("delete_report_endpoint", "report"),
        ("delete_quiz_endpoint", "quiz"),
    ],
)
def test_retired_delete_endpoints_cannot_mutate_course_resources(
    tmp_path, endpoint_name, material_type
):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        material_type,
        "shared-a",
        {"title": "Course shared resource"},
        owner_user_id="teacher-a",
        visibility="course",
    )

    endpoint = getattr(teacher_api, endpoint_name)
    with pytest.raises(teacher_api.HTTPException) as raised:
        asyncio.run(
            endpoint(
                "shared-a",
                course_id="course-1",
                current_user={"username": "student-x", "role": "student"},
            )
        )

    assert raised.value.status_code == 410
    assert manager.get_stored_generated_material(
        "course-1", material_type, "shared-a"
    ) is not None
