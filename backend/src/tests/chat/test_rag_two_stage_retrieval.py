import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from modules.rag_v2.rag_main.system import RAGSystem
from modules.rag_v2.rag_main.core.config import Config

def make_rag():
    rag = RAGSystem.__new__(RAGSystem)
    rag.document_index = {
        "tree": {"file_name": "二叉树.pdf", "source_key": "s-tree"},
        "sort": {"file_name": "排序.pdf", "source_key": "s-sort"},
        "disabled": {"file_name": "二叉树.pdf", "include_in_search": False},
        "deleted": {"file_name": "二叉树.pdf", "status": "deleted"},
        "private": {"file_name": "私有.pdf"}}
    return rag

@pytest.mark.parametrize("enhanced", [False, True])
def test_order_and_scope(monkeypatch, enhanced):
    monkeypatch.setattr(Config, "RAG_DOCUMENT_SELECTION_ENABLED", True)
    rag = make_rag()
    order = []
    def model(**kwargs):
        order.append("select")
        assert kwargs["llm_config"]["timeout_seconds"] == Config.RAG_DOCUMENT_SELECTION_TIMEOUT
        return '{"status":"selected","selected_ids":["d1"]}'
    def retrieve(*args, **kwargs):
        order.append("retrieve")
        assert set(kwargs["allowed_sources"]) == {"tree", "s-tree"}
        return [{"metadata": {"source": "s-tree"}, "content": "TREE"},
                {"metadata": {"source": "s-sort"}, "content": "SORT"}]
    rag._call_llm = model
    rag.retrieve_documents = retrieve
    rag.embedding_client = SimpleNamespace(embed_query=lambda _: [1])
    rag.vector_store = SimpleNamespace(enhanced_hybrid_search_with_hyde=retrieve)
    chunks, trace = rag.retrieve_two_stage("二叉树", allowed_sources=["tree", "sort", "disabled", "deleted"], use_enhanced_retrieval=enhanced)
    assert order == ["select", "retrieve"]
    assert [c["content"] for c in chunks] == ["TREE"]
    assert trace["candidate_count"] == 2

def test_empty_scope():
    chunks, trace = make_rag().retrieve_two_stage("树", allowed_sources=[])
    assert chunks == []
    assert trace["selector_call_count"] == 0

def test_empty_chunks_no_retry():
    rag = make_rag()
    calls = []
    rag.retrieve_documents = lambda *a, **kw: calls.append(kw) or []
    chunks, trace = rag.retrieve_two_stage("树", allowed_sources=["s-tree"])
    assert chunks == []
    assert len(calls) == 1
    assert set(calls[0]["allowed_sources"]) == {"tree", "s-tree"}

def test_disabled_selector_keeps_authorized_scope(monkeypatch):
    monkeypatch.setattr(Config, "RAG_DOCUMENT_SELECTION_ENABLED", False)
    rag = make_rag()
    calls = []
    rag.retrieve_documents = lambda *a, **kw: calls.append(kw) or []
    _, trace = rag.retrieve_two_stage("树", allowed_sources=["tree", "sort"])
    assert set(calls[0]["allowed_sources"]) == {"tree", "s-tree", "sort", "s-sort"}
    assert trace["selector_call_count"] == 0


def test_query_without_rag_never_retrieves():
    rag = make_rag()
    rag._call_llm = lambda **kw: "普通回答"
    result = rag.query("你好", use_rag=False)
    assert result["answer"] == "普通回答"
    assert result["sources"] == []


def test_query_applies_owner_and_manual_scope_before_selection(monkeypatch):
    monkeypatch.setattr(Config, "RAG_DOCUMENT_SELECTION_ENABLED", True)
    rag = make_rag()
    rag.document_index["tree"]["owner"] = "alice"
    rag.document_index["sort"]["owner"] = "bob"
    rag._rewrite_query = lambda question, history: question
    rag._call_llm = lambda **kw: "回答"
    calls = []
    rag.retrieve_documents = lambda *a, **kw: calls.append(kw) or []
    rag.query("树", owner="alice", selected_doc_ids=["tree", "sort"])
    assert set(calls[0]["allowed_sources"]) == {"tree", "s-tree"}
