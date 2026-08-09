from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.runtime.tool_registry import build_tool_registry
from app.chat.tools.agent_tools import (
    get_tool_registry_for_capability,
    rag_search_tool,
    web_search_tool,
)


def test_tool_registry_exposes_no_tools_when_all_capabilities_disabled():
    registry = build_tool_registry(CapabilityPolicy())

    assert registry == {}


def test_tool_registry_exposes_rag_only_when_allow_rag_enabled():
    registry = build_tool_registry(
        CapabilityPolicy(
            allow_rag=True,
            allow_tools=True,
            selected_doc_ids=["doc-1"],
        )
    )

    assert "rag_search" in registry
    assert "deep_research" not in registry


def test_agent_tool_registry_excludes_external_tools_when_not_allowed():
    registry = get_tool_registry_for_capability(allow_rag=False, allow_web=False)

    assert "rag_search_tool" not in registry
    assert "web_search_tool" not in registry
    assert "generate_long_report_content" in registry


def test_agent_tool_registry_includes_authorized_external_tools():
    registry = get_tool_registry_for_capability(allow_rag=True, allow_web=False)

    assert "rag_search_tool" in registry
    assert "web_search_tool" not in registry


def test_web_search_tool_uses_bocha_basic_without_rag_import(monkeypatch):
    calls = []

    def fake_run_deepsearch_and_crawl(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "query": kwargs["query"],
            "links": ["https://example.com/a"],
            "results": [
                {"title": "Web A", "url": "https://example.com/a", "content": "Bocha summary A"}
            ],
            "summary": "Bocha summary A",
            "sources": [{"title": "Web A", "url": "https://example.com/a"}],
        }

    monkeypatch.setattr(
        "app.chat.tools.agent_tools.run_deepsearch_and_crawl",
        fake_run_deepsearch_and_crawl,
        raising=False,
    )

    result = web_search_tool(query="search topic", owner="teacher-a")

    assert result["ok"] is True
    assert result["payload"]["summary"] == "Bocha summary A"
    assert result["payload"]["answer"] == "Bocha summary A"
    assert result["payload"]["sources"] == [{"title": "Web A", "url": "https://example.com/a"}]
    assert result["payload"]["links"] == ["https://example.com/a"]
    assert result["payload"]["trace"] == {
        "web_links_count": 1,
        "web_sources_count": 1,
    }
    assert calls == [
        {
            "query": "search topic",
            "owner": "teacher-a",
            "depth": "basic",
            "save_to_kb": False,
        }
    ]


def test_rag_search_tool_resolves_course_relative_path_before_query(monkeypatch):
    class DummyRagSystem:
        def __init__(self):
            self.file_path = "D:/course/lesson.md"
            self.document_index = {
                "index-key": {
                    "physical_path": self.file_path,
                    "path": "knowledge_base/documents/lesson.md",
                    "source_key": "source-key",
                    "file_name": "lesson.md",
                    "owner": None,
                },
            }
            self.calls = []

        def _make_index_key(self, path, owner):
            if str(path) in {self.file_path, "index-key"}:
                return "index-key"
            return str(path)

        def _make_source_key(self, path, owner):
            return "source-key"

        def list_documents(self, owner=None):
            if owner != "teacher-a":
                return []
            return [{"file_path": "index-key", "file_name": "lesson.md", "owner": None}]

        def query(self, query, top_k=5, use_rag=True, selected_doc_ids=None, owner=None):
            self.calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "use_rag": use_rag,
                    "selected_doc_ids": list(selected_doc_ids or []),
                    "owner": owner,
                }
            )
            return {"answer": "ok", "sources": []}

    rag_system = DummyRagSystem()
    monkeypatch.setattr("app.chat.tools.agent_tools.get_rag_system", lambda: rag_system)

    result = rag_search_tool(
        query="what is a variable",
        selected_doc_ids=["knowledge_base/documents/lesson.md"],
        owner="teacher-a",
    )

    assert result["ok"] is True
    assert rag_system.calls == [
        {
            "query": "what is a variable",
            "top_k": 5,
            "use_rag": True,
            "selected_doc_ids": ["index-key"],
            "owner": "teacher-a",
        }
    ]


def test_rag_search_tool_passes_course_scope_to_public_id_resolver(monkeypatch):
    class DummyRagSystem:
        def query(self, query, top_k=5, use_rag=True, selected_doc_ids=None, owner=None):
            return {
                "answer": "链表通过指针连接节点。",
                "sources": [{"source": "linked-list.md", "content": "链表节点"}],
            }

    seen = {}
    monkeypatch.setattr("app.chat.tools.agent_tools.get_rag_system", lambda: DummyRagSystem())

    def fake_resolve(rag_system, selected_doc_ids, *, owner, course_id=None):
        seen.update(selected_doc_ids=selected_doc_ids, owner=owner, course_id=course_id)
        return ["resolved-linked-list-key"]

    monkeypatch.setattr(
        "app.chat.tools.agent_tools.resolve_selected_doc_ids_for_query",
        fake_resolve,
    )

    result = rag_search_tool(
        query="链表如何实现",
        selected_doc_ids=["https://example.com/linked-list/"],
        owner="teacher",
        course_id="computational-thinking",
    )

    assert result["ok"] is True
    assert seen == {
        "selected_doc_ids": ["https://example.com/linked-list/"],
        "owner": "teacher",
        "course_id": "computational-thinking",
    }
