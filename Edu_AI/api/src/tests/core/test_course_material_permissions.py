from core.course_storage import CourseStorageManager


def test_owned_material_is_hidden_from_other_users(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "quiz",
        "quiz-1",
        {"title": "私有测验"},
        owner_user_id="teacher-a",
    )

    assert manager.get_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    ) is None
    assert manager.list_generated_materials(
        "course-1", owner_user_id="teacher-b"
    ) == []
    assert manager.pin_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    ) is False
    assert manager.rename_generated_material(
        "course-1", "quiz", "quiz-1", "越权改名", owner_user_id="teacher-b"
    ) is False
    assert manager.delete_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    ) is False


def test_unowned_legacy_material_is_hidden_until_explicitly_assigned(tmp_path):
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

    assert manager.get_generated_material(
        "course-1", "report", "legacy-report", owner_user_id="teacher-a"
    ) is None
    assert manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a"
    ) == []


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
