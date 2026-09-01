from __future__ import annotations

import json
from pathlib import Path

from app.chat.memory.domain import (
    MemoryEvalReport,
    MemoryRecordDraft,
    RetrievalEvalReport,
)


def evaluate_candidate_extractor(dataset: Path, extractor) -> MemoryEvalReport:
    tp = fp = fn = 0
    protected_total = protected_rejected = 0
    case_count = 0
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case_count += 1
        case = json.loads(line)
        expected = set(case.get("expected_types") or [])
        actual = {
            candidate.memory_type for candidate in extractor.extract(case["message"])
        }
        tp += len(expected & actual)
        fp += len(actual - expected)
        fn += len(expected - actual)
        if case.get("protected"):
            protected_total += 1
            if not actual:
                protected_rejected += 1

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return MemoryEvalReport(
        case_count=case_count,
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        false_write_rate=fp / case_count if case_count else 0.0,
        protected_fact_rejection_rate=(
            protected_rejected / protected_total if protected_total else 1.0
        ),
    )


def evaluate_retrieval(dataset: Path, repository) -> RetrievalEvalReport:
    cases = [
        json.loads(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for case in cases:
        for index, item in enumerate(case["memories"]):
            repository.upsert_memory(
                MemoryRecordDraft(
                    subject_user_id=item.get(
                        "subject_user_id", case["subject_user_id"]
                    ),
                    owner_user_id=item.get("subject_user_id", case["subject_user_id"]),
                    course_id=item.get("course_id", case.get("course_id")),
                    conversation_id=f"eval-{case['id']}",
                    memory_type="episode",
                    fact_kind="summary",
                    content=item["content"],
                    confidence=0.95,
                    source_type="conversation",
                    source_id=item.get("source_id", f"{case['id']}:{index}"),
                    source_span=item["content"],
                )
            )

    hit_1 = hit_3 = 0
    reciprocal_rank = 0.0
    isolation_violations = 0
    for case in cases:
        expected = set(case["expected_source_ids"])
        results = repository.search(
            subject_user_id=case["subject_user_id"],
            course_id=case.get("course_id"),
            query=case["query"],
            limit=3,
        )
        source_ids = [item.source_id for item in results]
        if expected & set(source_ids[:1]):
            hit_1 += 1
        if expected & set(source_ids[:3]):
            hit_3 += 1
        for rank, source_id in enumerate(source_ids, start=1):
            if source_id in expected:
                reciprocal_rank += 1.0 / rank
                break
        if any(not source_id.startswith(f"{case['id']}:") for source_id in source_ids):
            isolation_violations += 1

    total = len(cases)
    return RetrievalEvalReport(
        case_count=total,
        recall_at_1=hit_1 / total if total else 0.0,
        recall_at_3=hit_3 / total if total else 0.0,
        mean_reciprocal_rank=reciprocal_rank / total if total else 0.0,
        isolation_violation_rate=isolation_violations / total if total else 0.0,
    )
