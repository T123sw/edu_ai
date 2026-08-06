from core.course_storage import CourseStorageManager


def test_course_material_is_visible_and_manageable_by_other_course_editors(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "quiz",
        "quiz-1",
        {"title": "共享测验"},
        owner_user_id="teacher-a",
    )

    material = manager.get_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    )
    assert material["created_by"] == "teacher-a"
    assert material["visibility"] == "course"
    assert [item["material_id"] for item in manager.list_generated_materials(
        "course-1", owner_user_id="teacher-b"
    )] == ["quiz-1"]
    assert manager.pin_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    ) is True
    assert manager.rename_generated_material(
        "course-1", "quiz", "quiz-1", "越权改名", owner_user_id="teacher-b"
    ) is True


def test_unowned_legacy_material_defaults_to_course_visibility(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    legacy_dir = (
        manager.get_course_dir("course-1") / "generated_materials" / "reports"
    )
    legacy_dir.mkdir(parents=True, exist_ok=True)
    manager._write_json(
        legacy_dir / "legacy-report.json",
        {"title": "历史报告", "material_type": "report"},
    )

    material = manager.get_generated_material(
        "course-1", "report", "legacy-report", owner_user_id="teacher-a"
    )
    assert material["visibility"] == "course"
    assert material["created_by"] is None


def test_private_material_still_requires_creator(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "quiz",
        "draft-1",
        {"title": "Private draft"},
        owner_user_id="teacher-a",
        visibility="private",
    )

    assert manager.get_generated_material(
        "course-1", "quiz", "draft-1", owner_user_id="teacher-b"
    ) is None
    assert manager.get_generated_material(
        "course-1", "quiz", "draft-1", owner_user_id="teacher-a"
    )["visibility"] == "private"


def test_complete_delete_removes_manifest_attachment_and_classroom_media(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "classroom",
        "classroom-1",
        {"title": "课堂", "file_extension": ".html"},
        file_data=b"<html></html>",
        owner_user_id="teacher-a",
    )
    media = manager.get_classroom_video_dir("course-1", "classroom-1")
    media.mkdir(parents=True, exist_ok=True)
    (media / "classroom.mp4").write_bytes(b"video")

    assert manager.delete_generated_material(
        "course-1", "classroom", "classroom-1", owner_user_id="teacher-a"
    ) is True
    assert manager.get_generated_material(
        "course-1", "classroom", "classroom-1", owner_user_id="teacher-a"
    ) is None
    assert media.exists() is False
