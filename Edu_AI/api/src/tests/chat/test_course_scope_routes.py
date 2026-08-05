import io
import sys
from pathlib import Path
import uuid

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import courses
from app.api import courses as courses_api
from app.services import course_service
from core.course_storage import CourseStorageManager


def _make_manager(name: str) -> CourseStorageManager:
    root = Path("tests/.tmp") / f"{name}-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    manager = CourseStorageManager(root_path=str(root))
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})
    return manager


def test_get_course_materials_returns_paginated_aggregate_scope(monkeypatch):
    manager = _make_manager("course-material-scope")
    for index in range(25):
        manager.save_generated_material(
            "course-1",
            "report",
            f"report-{index:02d}",
            {"title": f"report-{index:02d}"},
            scope_type="course" if index % 2 == 0 else "knowledge_point",
            scope_id=None if index % 2 == 0 else f"kp-{index:02d}",
        )

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    payload = courses.get_course_materials(
        "course-1",
        material_type="report",
        scope_type="course",
        scope_id=None,
        aggregate=True,
        limit=20,
        offset=20,
        current_user={"username": "teacher-a"},
    )

    assert payload["total"] == 25
    assert payload["count"] == 5
    assert payload["limit"] == 20
    assert payload["offset"] == 20


def test_get_knowledge_base_documents_filters_descendant_scope(monkeypatch):
    manager = _make_manager("course-doc-scope")
    manager.save_knowledge_graph(
        "course-1",
        {
            "id": "root",
            "children": [
                {
                    "id": "sorting",
                    "children": [{"id": "bubble", "children": []}],
                },
                {"id": "graphs", "children": []},
            ],
        },
    )
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
    manager.save_knowledge_base_file(
        "course-1",
        b"graphs",
        "graphs.md",
        scope_type="knowledge_point",
        scope_id="graphs",
    )

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    documents = courses.get_knowledge_base_documents(
        "course-1",
        scope_type="knowledge_point",
        scope_id="sorting",
        aggregate=False,
        current_user={"username": "teacher-a"},
    )

    assert [item.name for item in documents] == ["sorting.md", "bubble.md"]
    assert [item.scope_id for item in documents] == ["sorting", "bubble"]


def test_get_knowledge_base_documents_keeps_personal_library_current_node_only(monkeypatch):
    manager = _make_manager("course-doc-library")
    manager.save_knowledge_graph(
        "course-1",
        {
            "id": "root",
            "children": [
                {
                    "id": "sorting",
                    "children": [{"id": "bubble", "children": []}],
                },
            ],
        },
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

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    course_documents = courses.get_knowledge_base_documents(
        "course-1",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="course",
        include_descendants=True,
        current_user={"username": "teacher-a"},
    )
    personal_documents = courses.get_knowledge_base_documents(
        "course-1",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="personal",
        include_descendants=False,
        current_user={"username": "teacher-a"},
    )

    assert [item.name for item in course_documents] == ["course-child.md"]
    assert [item.name for item in personal_documents] == ["personal-parent.md"]


def test_get_knowledge_base_documents_returns_local_path_for_web_documents(monkeypatch):
    manager = _make_manager("course-doc-web-path")
    relative_path = manager.save_knowledge_base_file(
        "course-1",
        b"# page\n\nweb content",
        "support-page.md",
        scope_type="knowledge_point",
        scope_id="variables",
        library_type="personal",
        owner_user_id="teacher-a",
    )
    index = manager.get_knowledge_base_index("course-1")
    index[-1]["url"] = "https://support.microsoft.com/example"
    index[-1]["source_url"] = "https://support.microsoft.com/example"
    index[-1]["doc_kind"] = "web"
    manager.save_knowledge_base_index("course-1", index)

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    documents = courses.get_knowledge_base_documents(
        "course-1",
        scope_type="knowledge_point",
        scope_id="variables",
        library_type="personal",
        include_descendants=False,
        current_user={"username": "teacher-a"},
    )

    assert len(documents) == 1
    assert documents[0].type == "web"
    assert documents[0].url == "https://support.microsoft.com/example"
    assert documents[0].file_path == relative_path.replace("\\", "/")


@pytest.mark.anyio
async def test_add_rag_document_to_course_kb_accepts_course_relative_personal_document(monkeypatch):
    manager = _make_manager("course-doc-promote")
    relative_path = manager.save_knowledge_base_file(
        "course-1",
        b"personal",
        "personal.md",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="personal",
        owner_user_id="teacher-a",
    )

    class FakeRagSystem:
        def list_documents(self, owner=None):
            return []

        def import_document(
            self,
            path,
            force_reimport=False,
            progress_callback=None,
            owner=None,
        ):
            if progress_callback:
                progress_callback(100, "completed")
            return {"file": path}

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    monkeypatch.setattr(courses_api, "get_rag_system", lambda: FakeRagSystem())

    promoted = await courses.add_rag_document_to_course_kb(
        "course-1",
        courses.AddRAGDocumentRequest(
            rag_file_path=relative_path,
            scope_type="knowledge_point",
            scope_id="sorting",
            library_type="course",
            promoted_from_document_id="doc-personal-1",
        ),
        current_user={"username": "teacher-a"},
    )

    document = promoted["document"]
    assert document.name == "personal.md"
    assert document.library_type == "course"
    assert document.scope_id == "sorting"
    assert document.promoted_from_document_id == "doc-personal-1"
    assert promoted["job"]["kind"] == "rag_import"

    latest = manager.get_knowledge_base_index("course-1")[-1]
    assert latest["library_type"] == "course"
    assert latest["promoted_from_document_id"] == "doc-personal-1"


@pytest.mark.anyio
async def test_upload_knowledge_base_document_writes_selected_knowledge_point_scope(monkeypatch):
    manager = _make_manager("graph-node-upload")

    class FakeRagSystem:
        def import_document(self, file_path, force_reimport=False):
            return {"file": file_path}

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    monkeypatch.setattr(courses_api, "get_rag_system", lambda: FakeRagSystem())

    upload = courses.UploadFile(filename="sorting.md", file=io.BytesIO(b"sorting"))
    created = await courses.upload_knowledge_base_document(
        "course-1",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="course",
        file=upload,
        current_user={"username": "teacher-a"},
    )

    document = created["document"]
    assert document.library_type == "course"
    assert document.scope_type == "knowledge_point"
    assert document.scope_id == "sorting"
    assert document.status in {"received", "parsing", "indexing"}
    assert created["job"]["kind"] == "rag_import"

    latest = manager.get_knowledge_base_index("course-1")[-1]
    assert latest["scope_type"] == "knowledge_point"
    assert latest["scope_id"] == "sorting"
    assert latest["library_type"] == "course"


@pytest.mark.anyio
async def test_upload_knowledge_base_document_writes_course_root_scope_for_graph_root(monkeypatch):
    manager = _make_manager("graph-root-upload")

    class FakeRagSystem:
        def import_document(self, file_path, force_reimport=False):
            return {"file": file_path}

    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    monkeypatch.setattr(courses_api, "get_rag_system", lambda: FakeRagSystem())

    upload = courses.UploadFile(filename="root.md", file=io.BytesIO(b"root"))
    created = await courses.upload_knowledge_base_document(
        "course-1",
        scope_type="course",
        scope_id=None,
        library_type="course",
        file=upload,
        current_user={"username": "teacher-a"},
    )

    document = created["document"]
    assert document.library_type == "course"
    assert document.scope_type == "course"
    assert document.scope_id is None
    assert created["job"]["kind"] == "rag_import"

    latest = manager.get_knowledge_base_index("course-1")[-1]
    assert latest["scope_type"] == "course"
    assert latest["scope_id"] is None
    assert latest["library_type"] == "course"


def test_delete_knowledge_base_document_removes_index_entry_by_document_id(monkeypatch):
    manager = _make_manager("delete-kb-doc")
    relative_path = manager.save_knowledge_base_file(
        "course-1",
        b"doc",
        "delete-me.md",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="personal",
        owner_user_id="teacher-a",
    )
    document = manager.get_knowledge_base_index("course-1")[-1]
    absolute_path = manager.get_course_dir("course-1") / relative_path
    assert absolute_path.exists() is True

    class FakeRagSystem:
        def __init__(self):
            self.deleted = []

        def delete_document(self, path, owner=None):
            self.deleted.append(path)

    rag_system = FakeRagSystem()
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    monkeypatch.setattr(courses_api, "get_rag_system", lambda: rag_system)

    result = courses.delete_knowledge_base_document(
        "course-1",
        document["id"],
        current_user={"username": "teacher-a"},
    )

    assert result["message"]
    assert manager.get_knowledge_base_index("course-1") == []
    assert absolute_path.exists() is False
    assert rag_system.deleted == [str(absolute_path)]
