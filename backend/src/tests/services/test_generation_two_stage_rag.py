from types import SimpleNamespace
import pytest
from app.services.generation_task_handlers import _ResolvedDocumentContentReader, _generation_query
from app.services.classroom_service import fetch_course_rag_snippets
from modules.rag_v2.rag_main.system import RAGSystem
from modules.rag_v2.rag_main.core.config import Config


def test_resource_reader_uses_filtered_chunks(monkeypatch):
    monkeypatch.setattr(Config, "RAG_DOCUMENT_SELECTION_ENABLED", True)
    rag = RAGSystem.__new__(RAGSystem)
    rag.document_index = {"tree": {"file_name": "二叉树.pdf"}, "sort": {"file_name": "排序.pdf"}}
    rag._call_llm = lambda **kw: '{"status":"selected","selected_ids":["d1"]}'
    calls = []
    def retrieve(*a, **kw):
        calls.append(kw)
        return [{"content": "TREE", "metadata": {"source": "tree"}},
                {"content": "SORT", "metadata": {"source": "sort"}}]
    rag.retrieve_documents = retrieve
    monkeypatch.setattr("modules.rag_v2.api.get_rag_system", lambda: rag)
    result = _ResolvedDocumentContentReader().search_many(["tree", "sort"], "二叉树")
    assert "TREE" in result and "SORT" not in result
    assert calls[0]["allowed_sources"] == ["tree"]


def test_resource_query_combines_topic_and_requirements():
    assert _generation_query({"topic": "二叉树", "requirement": "生成遍历练习"}, "quiz") == "二叉树\n生成遍历练习"
    assert _generation_query({}, "quiz") == ""


@pytest.mark.parametrize("record", [{"include_in_search": False}, {"status": "deleted"}, {"library_type": "personal"}])
def test_classroom_catalog_excludes_unavailable_sources(record):
    manager = SimpleNamespace(get_knowledge_base_index=lambda _: [{"id": "x", **record}])
    assert fetch_course_rag_snippets(course_storage_manager=manager, course_id="c", query="树", rag_system=object()) is None
