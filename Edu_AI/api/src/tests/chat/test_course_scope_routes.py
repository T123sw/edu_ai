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
from app.services.course_access import CoursePrincipal
from app.services import course_service
from core.course_storage import CourseStorageManager


def _teacher_principal() -> CoursePrincipal:
    return CoursePrincipal(
        course_id="course-1",
        user_id="teacher-a",
        system_role="teacher",
        course_role="editor",
    )


def _principal(user_id: str, course_role: str) -> CoursePrincipal:
    return CoursePrincipal(
        course_id="course-1",
        user_id=user_id,
        system_role="student" if course_role == "viewer" else "teacher",
        course_role=course_role,
    )


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
        principal=CoursePrincipal(
            course_id="course-1",
            user_id="teacher-a",
            system_role="teacher",
            course_role="editor",
        ),
    )

    assert payload["total"] == 25
    assert payload["count"] == 5
    assert payload["limit"] == 20
    assert payload["offset"] == 20


def test_get_course_materials_filters_explicit_personal_and_course_spaces(monkeypatch):
    manager = _make_manager("course-material-spaces")
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
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    mine = courses.get_course_materials(
        "course-1", space="mine", principal=_principal("teacher-a", "editor")
    )
    shared = courses.get_course_materials(
        "course-1", space="course", principal=_principal("teacher-b", "editor")
    )

    assert [item["material_id"] for item in mine] == ["private-a"]
    assert [item["material_id"] for item in shared] == ["shared"]


def test_publish_route_requires_owner_and_course_resource_capability(monkeypatch):
    manager = _make_manager("course-material-publish-route")
    assert manager.save_generated_material(
        "course-1", "report", "private-a", {"title": "我的报告"},
        owner_user_id="teacher-a",
    )
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    published = courses.publish_course_material(
        "course-1",
        "report",
        "private-a",
        principal=_principal("teacher-a", "editor"),
    )
    assert published.action == "published"
    assert published.material["visibility"] == "course"

    with pytest.raises(courses.HTTPException) as other_teacher_error:
        courses.publish_course_material(
            "course-1",
            "report",
            "private-a",
            principal=_principal("teacher-b", "editor"),
        )
    assert other_teacher_error.value.status_code == 404
    assert other_teacher_error.value.detail["code"] == "MATERIAL_NOT_FOUND"

    with pytest.raises(courses.HTTPException) as viewer_error:
        courses.publish_course_material(
            "course-1",
            "report",
            "private-a",
            principal=_principal("student-a", "viewer"),
        )
    assert viewer_error.value.status_code == 403


def test_material_mutations_distinguish_private_owner_and_course_manager(monkeypatch):
    manager = _make_manager("course-material-aware-mutations")
    assert manager.save_generated_material(
        "course-1", "report", "private-a", {"title": "个人报告"},
        owner_user_id="teacher-a",
    )
    assert manager.save_generated_material(
        "course-1", "report", "shared", {"title": "课程报告"},
        owner_user_id="teacher-a", visibility="course",
    )
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)

    renamed_private = courses.rename_course_material(
        "course-1",
        "report",
        "private-a",
        courses.RenameMaterialRequest(title="我的修订"),
        principal=_principal("teacher-a", "editor"),
    )
    assert renamed_private["title"] == "我的修订"

    with pytest.raises(courses.HTTPException) as private_error:
        courses.rename_course_material(
            "course-1",
            "report",
            "private-a",
            courses.RenameMaterialRequest(title="越权修订"),
            principal=_principal("teacher-b", "editor"),
        )
    assert private_error.value.status_code == 404

    renamed_shared = courses.rename_course_material(
        "course-1",
        "report",
        "shared",
        courses.RenameMaterialRequest(title="协作修订"),
        principal=_principal("teacher-b", "editor"),
    )
    assert renamed_shared["title"] == "协作修订"

    with pytest.raises(courses.HTTPException) as viewer_error:
        courses.rename_course_material(
            "course-1",
            "report",
            "shared",
            courses.RenameMaterialRequest(title="学生修订"),
            principal=_principal("student-a", "viewer"),
        )
    assert viewer_error.value.status_code == 403


def test_withdraw_route_removes_publication_but_keeps_private_source(monkeypatch):
    manager = _make_manager("course-material-withdraw-route")
    assert manager.save_generated_material(
        "course-1", "report", "private-a", {"title": "个人报告"},
        owner_user_id="teacher-a",
    )
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    published = courses.publish_course_material(
        "course-1",
        "report",
        "private-a",
        principal=_principal("teacher-a", "editor"),
    )

    result = courses.withdraw_course_material(
        "course-1",
        "report",
        published.material["material_id"],
        principal=_principal("teacher-b", "editor"),
    )

    assert result == {"ok": True}
    assert manager.get_generated_material(
        "course-1", "report", "private-a", owner_user_id="teacher-a"
    ) is not None
    assert manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="course"
    ) == []


def test_generic_delete_routes_publication_through_withdraw(monkeypatch):
    manager = _make_manager("course-material-generic-withdraw")
    assert manager.save_generated_material(
        "course-1", "report", "private-a", {"title": "个人报告"},
        owner_user_id="teacher-a",
    )
    monkeypatch.setattr(course_service, "_get_manager", lambda: manager)
    published = courses.publish_course_material(
        "course-1",
        "report",
        "private-a",
        principal=_principal("teacher-a", "editor"),
    )

    result = courses.delete_course_material(
        "course-1",
        "report",
        published.material["material_id"],
        principal=_principal("teacher-b", "editor"),
    )

    assert result == {"ok": True}
    source = manager.get_generated_material(
        "course-1", "report", "private-a", owner_user_id="teacher-a"
    )
    assert source["published_material_id"] is None
    assert source["published_version"] is None
    assert manager.get_stored_generated_material(
        "course-1", "report", published.material["material_id"]
    ) is None


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
        principal=_teacher_principal(),
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
        principal=_teacher_principal(),
    )
    personal_documents = courses.get_knowledge_base_documents(
        "course-1",
        scope_type="knowledge_point",
        scope_id="sorting",
        library_type="personal",
        include_descendants=False,
        principal=_teacher_principal(),
    )

    assert [item.name for item in course_documents] == ["course-child.md"]
    assert [item.name for item in personal_documents] == ["personal-parent.md"]


def test_get_knowledge_base_documents_hides_local_path_for_web_documents(monkeypatch):
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
        principal=_teacher_principal(),
    )

    assert len(documents) == 1
    assert documents[0].type == "web"
    assert documents[0].url == "https://support.microsoft.com/example"
    assert relative_path.replace("\\", "/").endswith("support-page.md")
    assert documents[0].file_path is None


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
        principal=_teacher_principal(),
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
        principal=_teacher_principal(),
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
        principal=_teacher_principal(),
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
        principal=_teacher_principal(),
    )

    assert result["message"]
    assert manager.get_knowledge_base_index("course-1") == []
    assert absolute_path.exists() is False
    assert rag_system.deleted == [str(absolute_path)]
