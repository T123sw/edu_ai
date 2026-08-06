import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.chat.application.knowledge_base_document_content_provider import KnowledgeBaseDocumentContentProvider
from app.chat.application.knowledge_base_summary_provider import KnowledgeBaseSummaryProvider


class FakeVectorStore:
    def __init__(self, source_key):
        self.source_key = source_key

    def get_documents_by_source(self, source_key):
        if source_key != self.source_key:
            return []
        return [
            {"content": "first chunk", "metadata": {"page": 1}},
            {"content": "second chunk", "metadata": {"page": 2}},
        ]


class FakeRAGSystem:
    def __init__(self):
        self.physical_path = r"D:\docs\alice\lesson.md"
        self.index_key = f"user_alice:{self.physical_path}"
        self.source_key = self.index_key
        self.public_physical_path = r"D:\course\shared\legacy-lesson.md"
        self.public_index_key = self.public_physical_path
        self.public_source_key = self.public_index_key
        self.summarize_calls = []
        self.vector_store = FakeVectorStore(self.source_key)
        self.document_index = {
            self.index_key: {
                "physical_path": self.physical_path,
                "source_key": self.source_key,
                "file_name": "lesson.md",
                "summary": "stored summary",
                "summary_updated_at": "2026-04-15T00:00:00",
                "imported_at": "2026-04-14T00:00:00",
                "owner": "alice",
            },
            self.public_index_key: {
                "physical_path": self.public_physical_path,
                "source_key": self.public_source_key,
                "file_name": "legacy-lesson.md",
                "summary": "",
                "summary_updated_at": "",
                "imported_at": "2026-04-14T00:00:00",
                "owner": None,
            }
        }

    def _make_index_key(self, file_path, owner):
        if str(file_path).startswith("user_"):
            return str(file_path)
        return f"user_{owner}:{file_path}" if owner else str(file_path)

    def _make_source_key(self, file_path, owner):
        return self._make_index_key(file_path, owner)

    def list_documents(self, owner=None):
        if owner != "alice":
            return []
        return [
            {
                "file_path": self.index_key,
                "file_name": "lesson.md",
                "summary": "stored summary",
                "summary_updated_at": "2026-04-15T00:00:00",
                "imported_at": "2026-04-14T00:00:00",
                "owner": "alice",
            },
            {
                "file_path": self.public_index_key,
                "file_name": "legacy-lesson.md",
                "summary": "",
                "summary_updated_at": "",
                "imported_at": "2026-04-14T00:00:00",
                "owner": None,
            },
        ]

    def summarize_document(self, file_path, force_refresh=False, owner=None):
        self.summarize_calls.append(
            {
                "file_path": file_path,
                "force_refresh": force_refresh,
                "owner": owner,
            }
        )
        if file_path == self.public_index_key and owner is None:
            return {
                "summary": "generated public summary",
                "summary_updated_at": "2026-04-16T00:00:00",
            }
        raise AssertionError("unexpected summarize_document call")


def test_summary_provider_resolves_legacy_physical_path_against_public_index_key():
    rag_system = FakeRAGSystem()
    provider = KnowledgeBaseSummaryProvider(rag_system_factory=lambda: rag_system)

    result = provider.get_selected_document_summaries(
        selected_doc_ids=[rag_system.physical_path],
        owner="alice",
    )

    assert result["fallback_used"] is False
    assert result["documents"][0]["doc_id"] == rag_system.physical_path
    assert result["documents"][0]["title"] == "lesson.md"
    assert result["documents"][0]["summary"] == "stored summary"


def test_content_provider_resolves_legacy_physical_path_against_public_index_key():
    rag_system = FakeRAGSystem()
    provider = KnowledgeBaseDocumentContentProvider(rag_system_factory=lambda: rag_system)

    result = provider.get_selected_document_contents(
        selected_doc_ids=[rag_system.physical_path],
        owner="alice",
    )

    assert result["fallback_used"] is False
    assert result["documents"][0]["title"] == "lesson.md"
    assert result["documents"][0]["content"] == "first chunk\n\nsecond chunk"


def test_content_provider_reads_resolved_rag_key_without_public_id_lookup():
    rag_system = FakeRAGSystem()
    provider = KnowledgeBaseDocumentContentProvider(
        rag_system_factory=lambda: rag_system
    )

    result = provider.get_resolved_document_contents(
        rag_index_keys=[rag_system.index_key]
    )

    assert result["documents"][0]["rag_index_key"] == rag_system.index_key
    assert result["documents"][0]["content"] == "first chunk\n\nsecond chunk"


def test_summary_provider_reads_resolved_rag_key_without_public_id_lookup():
    rag_system = FakeRAGSystem()
    provider = KnowledgeBaseSummaryProvider(rag_system_factory=lambda: rag_system)

    result = provider.get_resolved_document_summaries(
        rag_index_keys=[rag_system.index_key]
    )

    assert result["documents"][0]["rag_index_key"] == rag_system.index_key
    assert result["documents"][0]["summary"] == "stored summary"


def test_summary_provider_generates_summary_for_public_legacy_relative_path_without_user_prefix():
    rag_system = FakeRAGSystem()
    provider = KnowledgeBaseSummaryProvider(rag_system_factory=lambda: rag_system)

    result = provider.get_selected_document_summaries(
        selected_doc_ids=["knowledge_base/documents/legacy-lesson.md"],
        owner="alice",
    )

    assert result["fallback_used"] is False
    assert result["documents"][0]["title"] == "legacy-lesson.md"
    assert result["documents"][0]["summary"] == "generated public summary"
    assert rag_system.summarize_calls == [
        {
            "file_path": rag_system.public_index_key,
            "force_refresh": False,
            "owner": None,
        }
    ]
