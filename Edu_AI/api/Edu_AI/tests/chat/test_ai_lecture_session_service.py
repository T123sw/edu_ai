from pathlib import Path
import uuid

from core.course_storage import CourseStorageManager


def _temp_root() -> Path:
    root = Path("D:/Edu_AI_1/tmp/ai-lecture-session-service").resolve() / f"case-{uuid.uuid4().hex[:12]}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_course(manager: CourseStorageManager, course_id: str = "course-1") -> None:
    manager.create_course_structure(course_id)
    manager.save_course_info(
        course_id,
        {
            "id": course_id,
            "title": "计算思维",
            "description": "课程说明",
            "icon": "BookOutlined",
            "color": "#1677ff",
        },
    )


def test_storage_maps_ai_lecture_sessions_to_dedicated_directory():
    manager = CourseStorageManager(root_path=str(_temp_root()))
    _write_course(manager)

    assert manager.save_generated_material(
        "course-1",
        "ai_lecture_session",
        "ai-session-1",
        {
            "title": "AI 实时讲解",
            "content": {"session_snapshot_id": "snapshot-1"},
            "generation_state": {"status": "created"},
        },
    )

    material = manager.get_generated_material("course-1", "ai_lecture_session", "ai-session-1")
    assert material is not None
    assert material["material_type"] == "ai_lecture_session"
    assert material["material_id"] == "ai-session-1"
    assert (
        manager.get_course_dir("course-1")
        / "generated_materials"
        / "lecture_sessions"
        / "ai-session-1.json"
    ).exists()
