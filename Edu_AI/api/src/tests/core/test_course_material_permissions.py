from core.course_storage import CourseStorageManager


def test_new_owned_material_defaults_to_private_and_hides_from_other_users(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "quiz",
        "draft-1",
        {"title": "个人测验"},
        owner_user_id="teacher-a",
    )

    material = manager.get_generated_material(
        "course-1", "quiz", "draft-1", owner_user_id="teacher-a"
    )
    assert material["created_by"] == "teacher-a"
    assert material["visibility"] == "private"
    assert manager.get_generated_material(
        "course-1", "quiz", "draft-1", owner_user_id="teacher-b"
    ) is None
    assert manager.pin_generated_material(
        "course-1", "quiz", "draft-1", owner_user_id="teacher-b"
    ) is False
    assert manager.rename_generated_material(
        "course-1", "quiz", "draft-1", "越权改名", owner_user_id="teacher-b"
    ) is False


def test_explicit_course_material_is_visible_and_manageable_by_other_course_editors(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "quiz",
        "quiz-1",
        {"title": "共享测验"},
        owner_user_id="teacher-a",
        visibility="course",
    )

    material = manager.get_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    )
    assert material["visibility"] == "course"
    assert manager.pin_generated_material(
        "course-1", "quiz", "quiz-1", owner_user_id="teacher-b"
    ) is True


def test_material_spaces_filter_private_and_course_records_after_authorization(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1", "report", "private-a", {"title": "我的报告"},
        owner_user_id="teacher-a", visibility="private",
    )
    assert manager.save_generated_material(
        "course-1", "report", "private-b", {"title": "他人报告"},
        owner_user_id="teacher-b", visibility="private",
    )
    assert manager.save_generated_material(
        "course-1", "report", "shared", {"title": "课程报告"},
        owner_user_id="teacher-a", visibility="course",
    )

    mine = manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="mine"
    )
    shared = manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="course"
    )
    combined = manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="all"
    )

    assert [item["material_id"] for item in mine] == ["private-a"]
    assert [item["material_id"] for item in shared] == ["shared"]
    assert {item["material_id"] for item in combined} == {"private-a", "shared"}


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


def test_private_material_mutations_fail_closed_without_an_owner(tmp_path):
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

    assert manager.delete_generated_material(
        "course-1", "quiz", "draft-1"
    ) is False
    assert manager.pin_generated_material(
        "course-1", "quiz", "draft-1"
    ) is False
    assert manager.rename_generated_material(
        "course-1", "quiz", "draft-1", "Missing principal"
    ) is False
    assert manager.get_generated_material(
        "course-1", "quiz", "draft-1", owner_user_id="teacher-a"
    ) is not None


def test_trusted_storage_getter_can_load_private_manifest_for_domain_services(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1",
        "report",
        "draft-1",
        {"title": "Private draft"},
        owner_user_id="teacher-a",
    )

    stored = manager.get_stored_generated_material(
        "course-1", "report", "draft-1"
    )

    assert stored["material_id"] == "draft-1"
    assert stored["owner_user_id"] == "teacher-a"
    assert stored["visibility"] == "private"


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
