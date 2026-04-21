from pathlib import Path
import uuid

from core.course_storage import CourseStorageManager


def _make_manager(name: str) -> CourseStorageManager:
    root = Path("tests/.tmp") / f"{name}-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    manager = CourseStorageManager(root_path=str(root))
    manager.create_course_structure("course-1")
    return manager


def test_list_generated_materials_filters_by_knowledge_point_scope():
    manager = _make_manager("course-storage-material-scope")

    manager.save_generated_material(
        "course-1",
        "report",
        "root-report",
        {"title": "root report"},
        scope_type="course",
        scope_id=None,
    )
    manager.save_generated_material(
        "course-1",
        "report",
        "sorting-report",
        {"title": "sorting report"},
        scope_type="knowledge_point",
        scope_id="sorting",
    )
    manager.save_generated_material(
        "course-1",
        "report",
        "bubble-report",
        {"title": "bubble report"},
        scope_type="knowledge_point",
        scope_id="bubble",
    )
    manager.save_generated_material(
        "course-1",
        "report",
        "graphs-report",
        {"title": "graphs report"},
        scope_type="knowledge_point",
        scope_id="graphs",
    )

    materials = manager.list_generated_materials(
        "course-1",
        "report",
        scope_type="knowledge_point",
        scope_ids={"sorting", "bubble"},
    )

    assert [item["material_id"] for item in materials] == ["bubble-report", "sorting-report"]


def test_get_knowledge_base_index_supports_scope_filtering_and_aggregate():
    manager = _make_manager("course-storage-doc-scope")

    manager.save_knowledge_base_file(
        "course-1",
        b"root",
        "root.md",
        scope_type="course",
        scope_id=None,
    )
    manager.save_knowledge_base_file(
        "course-1",
        b"sorting",
        "sorting.md",
        scope_type="knowledge_point",
        scope_id="sorting",
    )
    manager.save_knowledge_base_file(
        "course-1",
        b"bubble",
        "bubble.md",
        scope_type="knowledge_point",
        scope_id="bubble",
    )

    root_only = manager.get_knowledge_base_index("course-1", scope_type="course", aggregate=False)
    aggregate = manager.get_knowledge_base_index("course-1", scope_type="course", aggregate=True)
    scoped = manager.get_knowledge_base_index(
        "course-1",
        scope_type="knowledge_point",
        scope_ids={"sorting", "bubble"},
    )

    assert [item["filename"] for item in root_only] == ["root.md"]
    assert [item["filename"] for item in aggregate] == ["root.md", "sorting.md", "bubble.md"]
    assert [item["filename"] for item in scoped] == ["sorting.md", "bubble.md"]


def test_get_knowledge_base_index_filters_course_and_personal_libraries_independently():
    manager = _make_manager("course-storage-doc-library")

    manager.save_knowledge_base_file(
        "course-1",
        b"course-parent",
        "course-parent.md",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="course",
    )
    manager.save_knowledge_base_file(
        "course-1",
        b"course-child",
        "course-child.md",
        scope_type="knowledge_point",
        scope_id="bubble",
        library_type="course",
    )
    manager.save_knowledge_base_file(
        "course-1",
        b"personal-parent",
        "personal-parent.md",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="personal",
        owner_user_id="teacher-a",
    )
    manager.save_knowledge_base_file(
        "course-1",
        b"personal-child",
        "personal-child.md",
        scope_type="knowledge_point",
        scope_id="bubble",
        library_type="personal",
        owner_user_id="teacher-a",
    )

    course_docs = manager.get_knowledge_base_index(
        "course-1",
        scope_type="knowledge_point",
        scope_ids={"sorting", "bubble"},
        library_type="course",
    )
    personal_docs = manager.get_knowledge_base_index(
        "course-1",
        scope_type="knowledge_point",
        scope_ids={"sorting"},
        library_type="personal",
        owner_user_id="teacher-a",
    )

    assert [item["filename"] for item in course_docs] == ["course-parent.md", "course-child.md"]
    assert [item["filename"] for item in personal_docs] == ["personal-parent.md"]
