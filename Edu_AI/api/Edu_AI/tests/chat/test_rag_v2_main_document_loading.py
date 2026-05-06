import sys
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app import main
from app.integrations import rag_client


def test_main_selected_document_loader_uses_rag_v2_resolver_only(monkeypatch):
    loaded = SimpleNamespace(file_name="lesson.md", content="lesson content")
    calls = []

    def fake_load_rag_document_content(rag_system, document_id, owner=None):
        calls.append((document_id, owner))
        return loaded if document_id == "user_alice:lesson.md" else None

    class LegacyTrapRAGSystem:
        @property
        def document_index(self):
            raise AssertionError("business layer must not inspect document_index directly")

        def _make_index_key(self, *args, **kwargs):
            raise AssertionError("business layer must not use legacy manual key fallback")

    monkeypatch.setattr(rag_client, "load_rag_document_content", fake_load_rag_document_content)

    documents = main._load_selected_rag_documents(
        LegacyTrapRAGSystem(),
        ["user_alice:lesson.md", "missing-doc"],
        owner="alice",
        log_prefix="Test",
    )

    assert documents == [{"file_name": "lesson.md", "content": "lesson content"}]
    assert calls == [("user_alice:lesson.md", "alice"), ("missing-doc", "alice")]
