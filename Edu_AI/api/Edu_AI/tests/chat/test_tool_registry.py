from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.runtime.tool_registry import build_tool_registry
from app.chat.tools.agent_tools import get_tool_registry_for_capability, web_search_tool


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


def test_web_search_tool_queries_rag_after_import(monkeypatch):
    class DummyRagSystem:
        def __init__(self):
            self.file_path = "D:/tmp/web-a.md"
            self.document_index = {
                "index-key": {
                    "physical_path": self.file_path,
                    "source_key": "source-key",
                    "file_name": "web-a.md",
                    "owner": "teacher-a",
                },
            }
            self.calls = []

        def _make_index_key(self, path, owner):
            return "index-key" if str(path) in {self.file_path, "index-key"} else str(path)

        def _make_source_key(self, path, owner):
            return "source-key"

        def list_documents(self, owner=None):
            if owner != "teacher-a":
                return []
            return [{"file_path": "index-key", "file_name": "web-a.md", "owner": owner}]

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
            return {
                "answer": "web rag summary",
                "sources": [{"source": "doc-web", "content": "chunk", "page": 1}],
            }

    rag_system = DummyRagSystem()

    monkeypatch.setattr(
        "app.chat.tools.agent_tools.run_deepsearch_pipeline",
        lambda *, query, owner=None: {
            "ok": True,
            "query": query,
            "links": ["https://example.com/a"],
            "imported": [
                {
                    "file_path": "D:/tmp/web-a.md",
                    "file_name": "web-a.md",
                    "url": "https://example.com/a",
                }
            ],
        },
        raising=False,
    )
    monkeypatch.setattr("app.chat.tools.agent_tools.get_rag_system", lambda: rag_system)

    result = web_search_tool(query="帮我在网上查找关羽的战绩", owner="teacher-a")

    assert result["ok"] is True
    assert result["payload"]["summary"] == "web rag summary"
    assert result["payload"]["answer"] == "web rag summary"
    assert result["payload"]["sources"][0]["source"] == "doc-web"
    assert result["payload"]["links"] == ["https://example.com/a"]
    assert result["payload"]["trace"] == {
        "web_links_count": 1,
        "web_imported_count": 1,
        "web_selected_doc_ids_count": 1,
        "web_sources_count": 1,
    }
    assert rag_system.calls == [
        {
            "query": "帮我在网上查找关羽的战绩",
            "top_k": 5,
            "use_rag": True,
            "selected_doc_ids": ["index-key"],
            "owner": "teacher-a",
        }
    ]
