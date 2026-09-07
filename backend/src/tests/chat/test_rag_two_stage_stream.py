import json
from types import SimpleNamespace
import pytest
from modules.rag_v2.rag_main import api
from modules.rag_v2.rag_main.system import RAGSystem
from modules.rag_v2.rag_main.core.config import Config

@pytest.mark.anyio
@pytest.mark.parametrize("enhanced", [False, True])
async def test_stream_runs_real_router_before_retrieval(monkeypatch, enhanced):
    monkeypatch.setattr(Config, "RAG_DOCUMENT_SELECTION_ENABLED", True)
    rag = RAGSystem.__new__(RAGSystem)
    rag.document_index = {
        "tree": {"owner": "alice", "file_name": "二叉树.pdf"},
        "sort": {"owner": "alice", "file_name": "排序.pdf"},
        "private": {"owner": "bob", "file_name": "二叉树.pdf"}}
    calls = []
    def model(**kwargs):
        if kwargs.get("stream"):
            return iter(["遍历回答"])
        calls.append("selection")
        assert "private" not in kwargs["messages"][1]["content"]
        return '{"status":"selected","selected_ids":["d1"]}'
    def retrieve(*a, **kwargs):
        calls.append("retrieval")
        assert kwargs["allowed_sources"] == ["tree"]
        return [{"content": "TREE", "metadata": {"source": "tree", "owner": "alice"}}]
    rag._call_llm = model
    rag._rewrite_query = lambda q, history: q
    rag.retrieve_documents = retrieve
    rag.embedding_client = SimpleNamespace(embed_query=lambda _: [1])
    rag.vector_store = SimpleNamespace(enhanced_hybrid_search_with_hyde=retrieve)
    monkeypatch.setattr(api, "get_rag_system", lambda: rag)
    response = await api.rag_query_stream(api.QueryRequest(question="二叉树", use_enhanced_retrieval=enhanced), current_user={"username": "alice"})
    body = "".join([chunk if isinstance(chunk, str) else chunk.decode() async for chunk in response.body_iterator])
    assert calls == ["selection", "retrieval"]
    assert "TREE" in body
    assert "private" not in body
