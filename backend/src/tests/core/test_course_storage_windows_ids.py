from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from core.course_storage import CourseStorageManager


def test_list_generated_materials_handles_windows_unsafe_material_ids():
    root_path = Path(__file__).resolve().parent / ".manual_course_storage" / uuid4().hex
    try:
        manager = CourseStorageManager(root_path=str(root_path))
        manager.create_course_structure("course-1")

        manager.save_generated_material(
            "course-1",
            "report",
            "conv-887d71fab7b1:content",
            {
                "title": "高一物理课堂观察报告.md",
                "material_type": "report",
                "created_at": "2026-04-06T18:05:40.447755",
                "report": "# 高一物理课堂观察报告\n\n正文",
            },
        )

        materials = manager.list_generated_materials("course-1", "report")

        assert len(materials) == 1
        assert materials[0]["material_id"] == "conv-887d71fab7b1__content"
        assert materials[0]["title"] == "高一物理课堂观察报告.md"
    finally:
        rmtree(root_path, ignore_errors=True)
