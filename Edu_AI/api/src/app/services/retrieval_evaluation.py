"""Repeatable offline evaluation for the production retrieval pipeline."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    query: str
    expected_source_contains: tuple[str, ...] = field(default_factory=tuple)
    expected_chunk_ids: tuple[str, ...] = field(default_factory=tuple)
    expected_node_ids: tuple[str, ...] = field(default_factory=tuple)
    requires_visual: bool = False


def _is_relevant(case: RetrievalCase, result: dict[str, Any]) -> bool:
    metadata = result.get("metadata") or {}
    chunk_id = str(metadata.get("chunk_id") or result.get("id") or "")
    if chunk_id and chunk_id in case.expected_chunk_ids:
        return True
    node_id = str(metadata.get("knowledge_node_id") or metadata.get("node_id") or "")
    if node_id and node_id in case.expected_node_ids:
        return True
    source_haystack = "\n".join(
        str(value or "").lower()
        for value in (
            metadata.get("document_name"),
            metadata.get("source"),
            result.get("source"),
        )
    )
    return any(needle.lower() in source_haystack for needle in case.expected_source_contains)


def evaluate_retrieval(
    rag_system: Any,
    cases: Iterable[RetrievalCase],
    *,
    allowed_sources: list[str],
    top_k: int = 10,
) -> dict[str, Any]:
    """Evaluate the same dense/BM25/RRF/rerank method used by production Q&A."""
    normalized_cases = list(cases)
    rows: list[dict[str, Any]] = []
    latencies: list[int] = []
    allowed = set(allowed_sources)
    recall_hits = 0
    reciprocal_rank_total = 0.0
    node_hits_at_5 = 0
    hit_counts = {1: 0, 3: 0, 5: 0, 10: 0}
    precision_totals = {5: 0.0, 10: 0.0}
    unique_document_total = 0
    returned_result_total = 0
    visual_total = 0
    visual_hits = 0
    leakage_count = 0
    embeddings = rag_system.embedding_client.embed_documents(
        [case.query for case in normalized_cases]
    ) if normalized_cases else []

    for case, query_embedding in zip(normalized_cases, embeddings):
        started = time.perf_counter()
        results = rag_system.retrieve_documents(
            case.query,
            top_k=top_k,
            allowed_sources=allowed_sources,
            query_embedding=query_embedding,
        )
        elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
        latencies.append(elapsed_ms)
        relevant_ranks = [
            rank
            for rank, result in enumerate(results, start=1)
            if _is_relevant(case, result)
        ]
        first_rank = relevant_ranks[0] if relevant_ranks else None
        for cutoff in hit_counts:
            if first_rank is not None and first_rank <= cutoff:
                hit_counts[cutoff] += 1
        for cutoff in precision_totals:
            relevant_count = sum(rank <= cutoff for rank in relevant_ranks)
            precision_totals[cutoff] += relevant_count / cutoff
        if first_rank is not None and first_rank <= top_k:
            recall_hits += 1
            reciprocal_rank_total += 1.0 / first_rank
        if first_rank is not None and first_rank <= 5:
            node_hits_at_5 += 1

        visual_hit = None
        if case.requires_visual:
            visual_total += 1
            visual_hit = any(
                str((result.get("metadata") or {}).get("modality", "text")).lower()
                in {"image", "video"}
                and _is_relevant(case, result)
                for result in results[:top_k]
            )
            if visual_hit:
                visual_hits += 1

        leaked = [
            str((result.get("metadata") or {}).get("source") or "")
            for result in results
            if str((result.get("metadata") or {}).get("source") or "") not in allowed
        ]
        leakage_count += len(leaked)
        returned_result_total += len(results)
        document_names = [
            str((result.get("metadata") or {}).get("document_name") or "")
            for result in results
        ]
        unique_document_count = len({name for name in document_names if name})
        unique_document_total += unique_document_count
        rows.append(
            {
                "case_id": case.case_id,
                "query": case.query,
                "first_relevant_rank": first_rank,
                "hit_at_5": bool(first_rank is not None and first_rank <= 5),
                "hit_at_10": bool(first_rank is not None and first_rank <= top_k),
                "visual_hit": visual_hit,
                "latency_ms": elapsed_ms,
                "relevant_results_at_5": sum(rank <= 5 for rank in relevant_ranks),
                "relevant_results_at_10": sum(rank <= 10 for rank in relevant_ranks),
                "unique_documents_at_10": unique_document_count,
                "leaked_sources": leaked,
                "result_sources": document_names,
            }
        )

    count = len(normalized_cases)
    sorted_latencies = sorted(latencies)
    p50_index = max(0, math.ceil(len(sorted_latencies) * 0.50) - 1) if sorted_latencies else 0
    p95_index = max(0, math.ceil(len(sorted_latencies) * 0.95) - 1) if sorted_latencies else 0
    return {
        "case_count": count,
        "top_k": top_k,
        "metrics": {
            "question_hit_at_1": round(hit_counts[1] / count, 4) if count else 0.0,
            "question_hit_at_3": round(hit_counts[3] / count, 4) if count else 0.0,
            "question_hit_at_5": round(hit_counts[5] / count, 4) if count else 0.0,
            "question_hit_at_10": round(hit_counts[10] / count, 4) if count else 0.0,
            "recall_at_10": round(recall_hits / count, 4) if count else 0.0,
            "mrr_at_10": round(reciprocal_rank_total / count, 4) if count else 0.0,
            "node_hit_at_5": round(node_hits_at_5 / count, 4) if count else 0.0,
            "macro_node_precision_at_5": (
                round(precision_totals[5] / count, 4) if count else 0.0
            ),
            "macro_node_precision_at_10": (
                round(precision_totals[10] / count, 4) if count else 0.0
            ),
            "mean_unique_documents_at_10": (
                round(unique_document_total / count, 2) if count else 0.0
            ),
            "visual_hit_at_10": (
                round(visual_hits / visual_total, 4) if visual_total else None
            ),
            "visual_case_count": visual_total,
            "visual_hit_count": visual_hits,
            "scope_leakage_count": leakage_count,
            "scope_leakage_rate": (
                round(leakage_count / returned_result_total, 6)
                if returned_result_total
                else 0.0
            ),
            "latency_mean_ms": (
                round(sum(latencies) / len(latencies)) if latencies else 0
            ),
            "latency_p50_ms": sorted_latencies[p50_index] if sorted_latencies else 0,
            "latency_p95_ms": sorted_latencies[p95_index] if sorted_latencies else 0,
        },
        "cases": rows,
    }
