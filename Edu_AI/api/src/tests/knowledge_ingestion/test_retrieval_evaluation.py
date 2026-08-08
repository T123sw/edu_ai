from __future__ import annotations

from app.services.retrieval_evaluation import RetrievalCase, evaluate_retrieval


class _FakeRag:
    def __init__(self, results):
        self.results = results
        self.calls = []
        self.embedding_client = self

    @staticmethod
    def embed_documents(texts):
        return [[float(index)] for index, _ in enumerate(texts)]

    def retrieve_documents(self, query, *, top_k, allowed_sources, query_embedding=None):
        self.calls.append((query, top_k, tuple(allowed_sources)))
        return self.results[query][:top_k]


def _doc(name: str, source: str, *, modality: str = "text"):
    return {
        "id": name,
        "content": name,
        "metadata": {
            "document_name": name,
            "source": source,
            "modality": modality,
        },
    }


def test_evaluator_computes_recall_mrr_visual_and_scope_leakage() -> None:
    rag = _FakeRag(
        {
            "问题一": [_doc("无关", "course:a"), _doc("快速排序教材", "course:b")],
            "问题二": [_doc("示意图", "course:c", modality="image")],
        }
    )
    report = evaluate_retrieval(
        rag,
        [
            RetrievalCase("c1", "问题一", expected_source_contains=("快速排序",)),
            RetrievalCase(
                "c2",
                "问题二",
                expected_source_contains=("示意图",),
                requires_visual=True,
            ),
        ],
        allowed_sources=["course:a", "course:b"],
        top_k=10,
    )

    assert report["metrics"]["recall_at_10"] == 1.0
    assert report["metrics"]["question_hit_at_1"] == 0.5
    assert report["metrics"]["question_hit_at_3"] == 1.0
    assert report["metrics"]["mrr_at_10"] == 0.75
    assert report["metrics"]["node_hit_at_5"] == 1.0
    assert report["metrics"]["macro_node_precision_at_5"] == 0.2
    assert report["metrics"]["macro_node_precision_at_10"] == 0.1
    assert report["metrics"]["mean_unique_documents_at_10"] == 1.5
    assert report["metrics"]["visual_hit_at_10"] == 1.0
    assert report["metrics"]["visual_case_count"] == 1
    assert report["metrics"]["visual_hit_count"] == 1
    assert report["metrics"]["scope_leakage_count"] == 1
    assert report["metrics"]["scope_leakage_rate"] == 0.333333
    assert rag.calls[0][1] == 10


def test_visual_hit_requires_a_relevant_visual_not_any_image() -> None:
    rag = _FakeRag(
        {
            "find tree diagram": [
                _doc("unrelated-network-image", "course:a", modality="image"),
                _doc("tree-notes", "course:b", modality="text"),
            ]
        }
    )

    report = evaluate_retrieval(
        rag,
        [
            RetrievalCase(
                "visual-tree",
                "find tree diagram",
                expected_source_contains=("tree-notes",),
                requires_visual=True,
            )
        ],
        allowed_sources=["course:a", "course:b"],
        top_k=10,
    )

    assert report["metrics"]["recall_at_10"] == 1.0
    assert report["metrics"]["visual_hit_at_10"] == 0.0
