from __future__ import annotations

from modules.rag_v2.rag_main import system as runtime_system


class _NoopReranker:
    @staticmethod
    def is_ready() -> bool:
        return False


def test_vector_candidate_recall_keeps_multiple_chunks_from_same_source() -> None:
    class Collection:
        @staticmethod
        def query(**kwargs):
            return {
                "documents": [["第一块", "第二块", "第三块"]],
                "metadatas": [[
                    {"source": "same-book", "chunk_id": "c1"},
                    {"source": "same-book", "chunk_id": "c2"},
                    {"source": "same-book", "chunk_id": "c3"},
                ]],
                "distances": [[1.21, 1.22, 1.23]],
                "ids": [["v1", "v2", "v3"]],
            }

    store = object.__new__(runtime_system.VectorStore)
    store.collection = Collection()

    results = store.search([0.1, 0.2], top_k=3, distance_threshold=1.5)

    assert [item["id"] for item in results] == ["v1", "v2", "v3"]


def test_hybrid_search_uses_rrf_and_rewards_multi_route_matches(monkeypatch) -> None:
    store = object.__new__(runtime_system.VectorStore)
    store.reranker = _NoopReranker()

    vector = [
        {"id": "a", "content": "仅语义命中", "metadata": {"source": "book-a"}, "distance": 0.4},
        {"id": "b", "content": "两路都命中", "metadata": {"source": "book-b"}, "distance": 0.5},
    ]
    keyword = [
        {"id": "b", "content": "两路都命中", "metadata": {"source": "book-b"}, "bm25_score": 12.0},
        {"id": "c", "content": "仅关键词命中", "metadata": {"source": "book-c"}, "bm25_score": 10.0},
    ]
    monkeypatch.setattr(store, "search", lambda *args, **kwargs: vector)
    monkeypatch.setattr(store, "keyword_search", lambda *args, **kwargs: keyword)
    monkeypatch.setattr(runtime_system, "BM25_AVAILABLE", True)

    results = store.hybrid_search("复杂度", [0.1], top_k=3)

    assert results[0]["id"] == "b"
    assert results[0]["rrf_score"] > results[1]["rrf_score"]


def test_rewritten_query_is_supplemental_instead_of_replacing_original(monkeypatch) -> None:
    store = object.__new__(runtime_system.VectorStore)
    store.reranker = _NoopReranker()
    dense_calls: list[tuple[float, ...]] = []
    keyword_calls: list[str] = []

    def dense(embedding, **kwargs):
        dense_calls.append(tuple(embedding))
        suffix = "original" if embedding == [1.0] else "rewrite"
        return [{"id": suffix, "content": suffix, "metadata": {"source": suffix}, "distance": 0.4}]

    def sparse(query, **kwargs):
        keyword_calls.append(query)
        return [{"id": query, "content": query, "metadata": {"source": query}, "bm25_score": 1.0}]

    monkeypatch.setattr(store, "search", dense)
    monkeypatch.setattr(store, "keyword_search", sparse)
    monkeypatch.setattr(runtime_system, "BM25_AVAILABLE", True)

    store.hybrid_search(
        "它的复杂度是什么",
        [1.0],
        top_k=4,
        additional_queries=[("快速排序的平均时间复杂度", [2.0])],
    )

    assert dense_calls == [(1.0,), (2.0,)]
    assert keyword_calls == ["它的复杂度是什么", "快速排序的平均时间复杂度"]


def test_parent_context_expansion_preserves_formula_and_markdown() -> None:
    index = {
        "course:doc": {
            "parent_chunks": {
                "p1": {
                    "heading_path": "算法 > 复杂度",
                    "content": "定义如下：\n\n$$T(n)=\\sum_{i=1}^{n}1=n$$\n\n| n | T(n) |\n|---|---|",
                }
            }
        }
    }
    child = {
        "id": "c1",
        "content": "短子块",
        "metadata": {"parent_id": "p1", "modality": "text"},
    }

    expanded = runtime_system._expand_parent_context(index, child, "course:doc")

    assert expanded["content"].startswith("【章节上下文】: 算法 > 复杂度")
    assert "\\sum" in expanded["content"]
    assert "|---|---|" in expanded["content"]
    assert expanded["metadata"]["context_expanded"] == "parent"


def test_visual_intent_reserves_an_image_from_the_top_knowledge_node(monkeypatch) -> None:
    store = object.__new__(runtime_system.VectorStore)
    store.reranker = _NoopReranker()

    text = {
        "id": "tree-text",
        "content": "二叉树节点层次",
        "metadata": {
            "source": "tree-book",
            "knowledge_node_id": "tree",
            "modality": "text",
        },
        "distance": 0.2,
    }
    image = {
        "id": "tree-image",
        "content": "[IMAGE_CHUNK] 二叉树层次图",
        "metadata": {
            "source": "tree-book",
            "knowledge_node_id": "tree",
            "modality": "image",
        },
        "distance": 0.5,
    }

    def dense(*args, **kwargs):
        return [image] if kwargs.get("modality_filter") == "image" else [text]

    monkeypatch.setattr(store, "search", dense)
    monkeypatch.setattr(store, "keyword_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(runtime_system, "BM25_AVAILABLE", False)

    results = store.hybrid_search("请给我一张二叉树结构示意图", [0.1], top_k=3)

    assert any((item.get("metadata") or {}).get("modality") == "image" for item in results)
    assert {item["metadata"]["knowledge_node_id"] for item in results} == {"tree"}
