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
