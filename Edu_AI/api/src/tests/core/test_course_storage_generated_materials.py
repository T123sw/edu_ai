import hashlib

from core.course_storage import CourseStorageManager


def test_classroom_qa_directory_hashes_owner(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))

    path = manager.get_classroom_qa_dir(
        'course-1',
        'classroom-1',
        'student@example.com',
    )

    assert path.name == hashlib.sha256(b'student@example.com').hexdigest()[:24]
    assert 'student@example.com' not in str(path)
    assert 'classroom-1_media' in str(path)


def test_list_generated_materials_sorts_pinned_first(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")

    manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {
            "title": "普通报告",
            "material_type": "report",
            "created_at": "2026-04-06T10:00:00",
        },
    )
    manager.save_generated_material(
        "course-1",
        "report",
        "report-2",
        {
            "title": "置顶报告",
            "material_type": "report",
            "created_at": "2026-04-06T09:00:00",
            "is_pinned": True,
            "pinned_at": "2026-04-06T11:00:00",
        },
    )

    materials = manager.list_generated_materials("course-1", "report")

    assert [item["material_id"] for item in materials] == ["report-2", "report-1"]


def test_pin_generated_material_updates_json_metadata(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    manager.save_generated_material(
        "course-1",
        "quiz",
        "quiz-1",
        {
            "title": "测验",
            "material_type": "quiz",
            "created_at": "2026-04-06T10:00:00",
        },
    )

    assert manager.pin_generated_material("course-1", "quiz", "quiz-1", is_pinned=True) is True

    stored = manager.get_generated_material("course-1", "quiz", "quiz-1")

    assert stored["is_pinned"] is True
    assert stored["pinned_at"]


def test_explicit_recent_sort_ignores_pin_priority(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    manager.save_generated_material(
        "course-1",
        "report",
        "older-pinned",
        {
            "title": "旧报告",
            "created_at": "2026-04-06T09:00:00",
            "updated_at": "2026-04-06T09:30:00",
            "is_pinned": True,
            "pinned_at": "2026-04-06T12:00:00",
        },
    )
    manager.save_generated_material(
        "course-1",
        "report",
        "newer",
        {
            "title": "新报告",
            "created_at": "2026-04-06T10:00:00",
            "updated_at": "2026-04-06T11:00:00",
        },
    )

    materials = manager.list_generated_materials(
        "course-1",
        "report",
        sort="updated_desc",
    )

    assert [item["material_id"] for item in materials] == [
        "newer",
        "older-pinned",
    ]


def test_name_sort_uses_natural_numeric_order(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    for material_id, title in (
        ("report-10", "报告 10"),
        ("report-2", "报告 2"),
        ("report-1", "报告 1"),
    ):
        manager.save_generated_material(
            "course-1",
            "report",
            material_id,
            {"title": title, "created_at": "2026-04-06T10:00:00"},
        )

    ascending = manager.list_generated_materials(
        "course-1",
        "report",
        sort="name_asc",
    )
    descending = manager.list_generated_materials(
        "course-1",
        "report",
        sort="name_desc",
    )

    assert [item["title"] for item in ascending] == [
        "报告 1",
        "报告 2",
        "报告 10",
    ]
    assert [item["title"] for item in descending] == [
        "报告 10",
        "报告 2",
        "报告 1",
    ]
