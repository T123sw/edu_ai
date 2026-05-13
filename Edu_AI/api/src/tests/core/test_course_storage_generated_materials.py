from core.course_storage import CourseStorageManager


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
