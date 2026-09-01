import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import main
from app.integrations import rag_client


class DummyRagSystem:
    pass


def test_resolve_selected_doc_ids_for_query_prefers_resolved_ids(monkeypatch):
    monkeypatch.setattr(
        rag_client,
        "resolve_rag_document_ids",
        lambda rag_system, selected_doc_ids, owner=None: ["index-key-1", "index-key-2"],
    )

    resolved = main._resolve_selected_doc_ids_for_query(
        DummyRagSystem(),
        ["knowledge_base/documents/a.md", "knowledge_base/documents/b.md"],
        owner="teacher",
    )

    assert resolved == ["index-key-1", "index-key-2"]


def test_resolve_selected_doc_ids_for_query_falls_back_to_original_ids_when_resolution_fails(monkeypatch):
    monkeypatch.setattr(
        rag_client,
        "resolve_rag_document_ids",
        lambda rag_system, selected_doc_ids, owner=None: [],
    )

    selected_doc_ids = ["knowledge_base/documents/a.md"]
    resolved = main._resolve_selected_doc_ids_for_query(
        DummyRagSystem(),
        selected_doc_ids,
        owner="teacher",
    )

    assert resolved == selected_doc_ids


def test_resolve_selected_doc_ids_for_query_maps_course_source_url_to_rag_key(monkeypatch):
    source_url = "https://example.com/linked-list/"
    rag_key = "user_teacher:D:/courses/course-1/linked-list.md"
    seen = {}

    class DummyStorageManager:
        def get_knowledge_base_index(self, course_id):
            assert course_id == "course-1"
            return [
                {
                    "id": "doc-v2-linked-list",
                    "source_url": source_url,
                    "path": "knowledge_base/documents-v2/linked-list.md",
                    "filename": "linked-list.md",
                    "rag_index_key": rag_key,
                }
            ]

    def fake_resolve(rag_system, selected_doc_ids, owner=None):
        seen["candidates"] = list(selected_doc_ids)
        seen["owner"] = owner
        return [rag_key] if rag_key in selected_doc_ids else []

    monkeypatch.setattr(rag_client, "storage_manager", DummyStorageManager())
    monkeypatch.setattr(rag_client, "resolve_rag_document_ids", fake_resolve)

    resolved = rag_client.resolve_selected_doc_ids_for_query(
        DummyRagSystem(),
        [source_url],
        owner="teacher",
        course_id="course-1",
    )

    assert resolved == [rag_key]
    assert source_url in seen["candidates"]
    assert "doc-v2-linked-list" in seen["candidates"]
    assert rag_key in seen["candidates"]
    assert seen["owner"] == "teacher"


def test_course_auto_resolves_only_ready_course_documents(monkeypatch):
    class DummyStorageManager:
        def get_knowledge_base_index(self, course_id):
            assert course_id == "course-1"
            return [
                {"id": "course-ready", "rag_index_key": "teacher:course-ready", "library_type": "course", "status": "ready"},
                {"id": "course-failed", "rag_index_key": "teacher:course-failed", "library_type": "course", "status": "failed"},
                {"id": "personal-ready", "rag_index_key": "student:personal-ready", "library_type": "personal", "status": "ready"},
            ]

    monkeypatch.setattr(rag_client, "storage_manager", DummyStorageManager())
    monkeypatch.setattr(rag_client, "resolve_rag_document_ids", lambda *args, **kwargs: [])

    resolved = rag_client.resolve_selected_doc_ids_for_query(
        DummyRagSystem(), [], owner="student", course_id="course-1"
    )

    assert "teacher:course-ready" in resolved
    assert "teacher:course-failed" not in resolved
    assert "student:personal-ready" not in resolved


def test_empty_course_auto_never_falls_back_to_all_owner_documents(monkeypatch):
    class DummyStorageManager:
        def get_knowledge_base_index(self, course_id):
            return []

    monkeypatch.setattr(rag_client, "storage_manager", DummyStorageManager())
    resolved = rag_client.resolve_selected_doc_ids_for_query(
        DummyRagSystem(), [], owner="student", course_id="empty-course"
    )
    assert resolved == ["__edu_ai_no_authorized_document__"]
