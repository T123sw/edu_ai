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


def test_online_textbook_is_mapped_to_multiple_leaf_nodes_at_required_confidence():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "高等数学",
            "children": [{
                "id": "module",
                "label": "微积分",
                "children": [
                    {"id": "limit", "label": "函数极限", "data": {"summary": "极限定义与计算"}, "children": []},
                    {"id": "derivative", "label": "导数", "data": {"summary": "导数定义与求导法则"}, "children": []},
                ],
            }],
        },
        "textbooks": [],
        "online_textbooks": [{
            "textbook_id": "online-book",
            "filename": "高等数学完整教材.pdf",
            "status": "ready",
            "source_url": "https://example.edu/calculus.pdf",
            "parse_result": {"chunks": [
                {"chunk_id": "limit-chapter", "chapter_title": "函数极限", "content": "函数极限的定义、性质与计算方法。", "content_hash": "limit-hash"},
                {"chunk_id": "derivative-chapter", "chapter_title": "导数", "content": "导数定义、求导法则和导函数。", "content_hash": "derivative-hash"},
            ]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    by_chunk = {item["chunk_id"]: item for item in result["mappings"]}
    assert by_chunk["limit-chapter"]["knowledge_node_id"] == "limit"
    assert by_chunk["derivative-chapter"]["knowledge_node_id"] == "derivative"
    assert all(item["mapping_confidence"] >= 0.25 for item in by_chunk.values())
    assert all(item["source_url"] == "https://example.edu/calculus.pdf" for item in by_chunk.values())


def test_ambiguous_semantic_mapping_is_not_counted_as_coverage():
    build = {
        "graph_draft": {
            "id": "root",
            "label": "Algebra",
            "children": [{
                "id": "module",
                "label": "Foundations",
                "children": [
                    {"id": "linear", "label": "Linear algebra", "data": {"summary": "algebra vector"}, "children": []},
                    {"id": "abstract", "label": "Abstract algebra", "data": {"summary": "algebra group"}, "children": []},
                ],
            }],
        },
        "textbooks": [{
            "textbook_id": "book-1", "filename": "book.md", "status": "ready",
            "parse_result": {"chunks": [{
                "chunk_id": "ambiguous", "chapter_title": "Algebra foundations",
                "content": "algebra concepts", "content_hash": "ambiguous-hash",
            }]},
        }],
    }

    result = map_textbook_chunks_to_graph(build)

    assert result["mappings"] == []
    assert result["unmapped"][0]["chunk_id"] == "ambiguous"
    assert result["unmapped"][0]["mapping_method"] == "ambiguous"
