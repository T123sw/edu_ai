"""classroom 落库单测（SPEC-02 §4/§6，对应 ACC-04 AC-04-5/7）：
校验失败拒绝落库、落库成功产出 result_ref、同 Stage.id 幂等 upsert。
"""

import sys
import uuid
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from core.course_storage import CourseStorageManager
from app.services.classroom_persistence import (
    ClassroomValidationError,
    persist_classroom_result,
)


def _make_manager() -> CourseStorageManager:
    root = Path("tests/.tmp") / f"classroom-persistence-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return CourseStorageManager(root_path=str(root))


def _valid_result():
    return {
        "id": "stage-1",
        "url": "http://sidecar-test:3000/classroom/stage-1",
        "createdAt": "2026-07-24T00:00:00.000Z",
        "scenesCount": 1,
        "stage": {"id": "stage-1", "name": "Retry Basics"},
        "scenes": [
            {
                "id": "scene-1",
                "type": "slide",
                "content": {
                    "type": "slide",
                    "canvas": {
                        "id": "slide-1",
                        "viewportRatio": 0.5625,
                        "elements": [{"id": "el-1", "type": "text"}],
                    },
                },
                "actions": [{"id": "act-1", "type": "speech", "text": "hello"}],
            }
        ],
    }


def test_persist_valid_result_returns_result_ref_and_saves_material():
    manager = _make_manager()
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})

    result_ref = persist_classroom_result(
        course_storage_manager=manager,
        course_id="course-1",
        owner="teacher-a",
        result=_valid_result(),
    )

    assert result_ref == {"classroom_id": "stage-1", "course_id": "course-1", "scenes_count": 1}

    saved = manager.get_generated_material("course-1", "classroom", "stage-1")
    assert saved is not None
    assert saved["title"] == "Retry Basics"
    assert saved["stage"]["id"] == "stage-1"
    assert len(saved["scenes"]) == 1
    assert saved["owner"] == "teacher-a"


def test_persist_invalid_result_raises_and_does_not_save():
    manager = _make_manager()
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})

    bad_result = _valid_result()
    del bad_result["stage"]["id"]
    del bad_result["id"]

    with pytest.raises(ClassroomValidationError):
        persist_classroom_result(
            course_storage_manager=manager,
            course_id="course-1",
            owner="teacher-a",
            result=bad_result,
        )

    assert manager.get_generated_material("course-1", "classroom", "stage-1") is None


def test_persist_same_stage_id_twice_upserts_not_duplicates():
    manager = _make_manager()
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})

    persist_classroom_result(
        course_storage_manager=manager, course_id="course-1", owner="teacher-a", result=_valid_result()
    )
    persist_classroom_result(
        course_storage_manager=manager, course_id="course-1", owner="teacher-a", result=_valid_result()
    )

    materials = manager.list_generated_materials("course-1", "classroom")
    assert len(materials) == 1
