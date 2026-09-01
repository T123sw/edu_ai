from app.chat.tools.agent_tools import rag_search_tool


def test_rag_search_tool_normalizes_image_sources_for_chat_runtime(monkeypatch):
    class DummyRagSystem:
        def query(self, query, top_k=5, use_rag=True, selected_doc_ids=None, owner=None):
            assert query == "根据图片资料回答"
            assert top_k == 3
            assert use_rag is True
            assert selected_doc_ids == ["doc-1"]
            assert owner == "teacher-a"
            return {
                "answer": "图片资料摘要",
                "sources": [
                    {
                        "source": "doc-image",
                        "content": "这是一张人物关系图",
                        "metadata": {
                            "modality": "image",
                            "image_path": r"D:\Edu_AI_1\backend\src\storage\images\teacher-a\diagram.png",
                            "source_path": r"D:\secret\teacher-a\diagram.png",
                        },
                    }
                ],
            }

    monkeypatch.setattr("app.chat.tools.agent_tools.get_rag_system", lambda: DummyRagSystem())

    result = rag_search_tool(
        query="根据图片资料回答",
        top_k=3,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
    )

    assert result["ok"] is True
    assert result["payload"]["answer"] == "图片资料摘要"
    source = result["payload"]["sources"][0]
    assert source["modality"] == "image"
    assert source["image_url"].endswith("path=images%2Fteacher-a%2Fdiagram.png")
    assert "image_path" not in source
    assert "source_path" not in source
    assert source["metadata"]["modality"] == "image"
    assert source["metadata"]["image_url"].endswith("path=images%2Fteacher-a%2Fdiagram.png")
    assert "image_path" not in source["metadata"]
    assert "source_path" not in source["metadata"]
