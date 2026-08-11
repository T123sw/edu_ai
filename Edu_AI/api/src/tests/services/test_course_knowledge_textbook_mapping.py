from __future__ import annotations

from app.services.course_knowledge_textbook_mapping import map_textbook_chunks_to_graph


def test_textbook_mapping_prefers_outline_anchor_then_semantic_overlap():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "代数",
            "children": [{
                "id": "module",
                "label": "模块",
                "children": [
                    {"id": "linear", "label": "一元方程", "data": {"summary": "方程求解", "source_outline_refs": ["chapter-1"]}, "children": []},
                    {"id": "function", "label": "一次函数", "data": {"summary": "函数图像与斜率"}, "children": []},
                ],
            }],
        },
        "textbooks": [{
            "textbook_id": "book-1",
            "filename": "教材.md",
            "status": "ready",
            "parse_result": {"chunks": [
                {"chunk_id": "c1", "chapter_id": "chapter-1", "chapter_title": "方程", "content": "解方程", "content_hash": "h1"},
                {"chunk_id": "c2", "chapter_id": "chapter-2", "chapter_title": "函数图像", "content": "一次函数图像的斜率", "content_hash": "h2"},
                {"chunk_id": "c3", "chapter_id": "appendix", "chapter_title": "附录", "content": "天气与地理", "content_hash": "h3"},
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    by_chunk = {item["chunk_id"]: item for item in result["mappings"]}
    assert by_chunk["c1"]["knowledge_node_id"] == "linear"
    assert by_chunk["c1"]["mapping_method"] == "outline_anchor"
    assert by_chunk["c2"]["knowledge_node_id"] == "function"
    assert result["unmapped"][0]["chunk_id"] == "c3"
