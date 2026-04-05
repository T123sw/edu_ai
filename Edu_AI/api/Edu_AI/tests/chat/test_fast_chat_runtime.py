from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.runtime.fast_chat_runtime import FastChatRuntime


class DummyGateway:
    def __init__(self):
        self.call_count = 0
        self.last_messages = None

    def chat(self, messages, temperature=0.2, max_tokens=1200):
        self.call_count += 1
        self.last_messages = messages
        return "test reply"


class DummyRetriever:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "ok": True,
            "payload": {
                "answer": "retrieved summary",
                "sources": [{"source": "doc-a", "content": "chunk text", "page": 1}],
            },
        }

    def __call__(self, *, query, top_k=5, selected_doc_ids=None, owner=None):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "selected_doc_ids": list(selected_doc_ids or []),
                "owner": owner,
            }
        )
        return self.result


def test_fast_runtime_builds_direct_reply():
    runtime = FastChatRuntime(model_gateway=DummyGateway())

    result = runtime.run(request=ChatRequestV2(question="hello"), snapshot=None, decision=None)

    assert result["message"]["content"] == "test reply"
    assert result["action"]["name"] == "chat.reply"
    assert result["conversation"]["conversation_id"] == ""


def test_fast_runtime_uses_recent_context_without_tools():
    gateway = DummyGateway()
    snapshot = SimpleNamespace(
        recent_messages=[{"role": "user", "content": "previous context"}],
        active_artifact=None,
    )
    runtime = FastChatRuntime(model_gateway=gateway)

    result = runtime.run(request=ChatRequestV2(question="continue"), snapshot=snapshot, decision=None)

    assert gateway.call_count == 1
    assert result["trace"]["path"] == "fast"
    assert result["sources"] == []


def test_fast_runtime_preserves_request_conversation_id():
    runtime = FastChatRuntime(model_gateway=DummyGateway())

    result = runtime.run(
        request=ChatRequestV2(question="hello", conversation_id="conv-fast"),
        snapshot=None,
        decision=None,
    )

    assert result["conversation"]["conversation_id"] == "conv-fast"


def test_fast_runtime_uses_rag_retriever_when_allowed():
    gateway = DummyGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="请根据知识库总结关羽生平",
        conversation_id="conv-rag",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_rag=True, selected_doc_ids=["doc-1"]),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert retriever.calls == [
        {
            "query": "请根据知识库总结关羽生平",
            "top_k": 5,
            "selected_doc_ids": ["doc-1"],
            "owner": "teacher-a",
        }
    ]
    assert result["sources"][0]["source"] == "doc-a"
    assert "retrieved summary" in gateway.last_messages[-1]["content"]


def test_fast_runtime_skips_rag_when_not_allowed():
    gateway = DummyGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(
        question="hello",
        conversation_id="conv-fast",
        capability=CapabilityPolicy(allow_rag=False, selected_doc_ids=["doc-1"]),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert retriever.calls == []
    assert result["sources"] == []


def test_fast_runtime_uses_web_retriever_when_allowed():
    gateway = DummyGateway()
    web_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [{"source": "https://example.com", "content": "web chunk", "page": 0}],
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, web_retriever=web_retriever)
    request = ChatRequestV2(
        question="请联网总结关羽生平",
        conversation_id="conv-web",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_web=True),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert web_retriever.calls == [
        {
            "query": "请联网总结关羽生平",
            "top_k": 5,
            "selected_doc_ids": [],
            "owner": "teacher-a",
        }
    ]
    assert result["sources"][0]["source"] == "https://example.com"
    assert "web summary" in gateway.last_messages[-1]["content"]


def test_fast_runtime_instructs_model_to_use_live_web_results_when_available():
    gateway = DummyGateway()
    web_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [{"source": "https://example.com", "content": "web chunk", "page": 0}],
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, web_retriever=web_retriever)
    request = ChatRequestV2(
        question="请联网总结关羽生平",
        conversation_id="conv-web",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_web=True),
    )

    runtime.run(request=request, snapshot=None, decision=None)

    assert "你当前已经拿到了联网检索结果" in gateway.last_messages[0]["content"]


def test_fast_runtime_exposes_web_trace_details():
    gateway = DummyGateway()
    web_retriever = DummyRetriever(
        {
            "ok": True,
            "payload": {
                "summary": "web summary",
                "sources": [
                    {"source": "https://example.com/a", "content": "web chunk", "page": 0},
                    {"source": "https://example.com/b", "content": "web chunk", "page": 0},
                ],
                "trace": {
                    "web_links_count": 8,
                    "web_imported_count": 6,
                    "web_selected_doc_ids_count": 12,
                },
            },
        }
    )
    runtime = FastChatRuntime(model_gateway=gateway, web_retriever=web_retriever)
    request = ChatRequestV2(
        question="请联网总结关羽生平",
        conversation_id="conv-web",
        owner="teacher-a",
        capability=CapabilityPolicy(allow_web=True),
    )

    result = runtime.run(request=request, snapshot=None, decision=None)

    assert result["trace"]["web_used"] is True
    assert result["trace"]["web_links_count"] == 8
    assert result["trace"]["web_imported_count"] == 6
    assert result["trace"]["web_selected_doc_ids_count"] == 12
    assert result["trace"]["web_sources_count"] == 2
