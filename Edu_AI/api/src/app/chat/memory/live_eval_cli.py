from __future__ import annotations

import json
import statistics
from pathlib import Path

from app.chat.memory.langmem_adapter import LangMemAdapter
from app.chat.memory.policy import MemoryWritePolicy
from app.chat.memory.settings import AgentMemorySettings
from core.config import Config


def main() -> None:
    if not Config.DEEP_MODEL_API_KEY:
        raise SystemExit("DEEP_MODEL_API_KEY is not configured")

    dataset = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "memory"
        / "memory_langmem_live_cases.jsonl"
    )
    cases = [
        json.loads(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    settings = AgentMemorySettings(
        enabled=True,
        langmem_enabled=True,
        langmem_background=False,
        langmem_timeout_ms=30_000,
        langmem_max_candidates=4,
        embedding_enabled=False,
    )
    adapter = LangMemAdapter(settings=settings)
    policy = MemoryWritePolicy(min_confidence=settings.min_confidence)

    tp = fp = fn = provider_errors = semantic_correct = 0
    positive_cases = 0
    latencies: list[int] = []
    case_results: list[dict] = []
    for case in cases:
        result = adapter.extract_candidates(
            messages=[
                {"role": "user", "content": case["message"]},
                {"role": "assistant", "content": "明白。"},
            ],
            existing_memories=[],
            policy_hint={"allowed_types": case.get("expected_types", [])},
        )
        latencies.append(result.latency_ms)
        if result.status == "error":
            provider_errors += 1

        accepted = []
        rejected = []
        for candidate in result.candidates:
            decision = policy.evaluate(candidate)
            reason = decision.reason
            allowed = decision.allowed
            if allowed and candidate.source_span not in case["message"]:
                allowed = False
                reason = "source_span_not_found"
            item = {
                "memory_type": candidate.memory_type,
                "profile_axis": candidate.profile_axis,
                "content": candidate.content,
                "source_span": candidate.source_span,
                "reason": reason,
            }
            (accepted if allowed else rejected).append(item)

        predicted_write = bool(accepted)
        expected_write = bool(case["should_write"])
        if predicted_write and expected_write:
            tp += 1
        elif predicted_write:
            fp += 1
        elif expected_write:
            fn += 1

        semantic_match = not expected_write
        if expected_write:
            positive_cases += 1
            expected_types = set(case.get("expected_types") or [])
            expected_axes = set(case.get("expected_axes") or [])
            type_match = any(item["memory_type"] in expected_types for item in accepted)
            axis_match = not expected_axes or any(
                item["profile_axis"] in expected_axes for item in accepted
            )
            semantic_match = type_match and axis_match
            semantic_correct += int(semantic_match)

        case_results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_write": expected_write,
                "provider_status": result.status,
                "latency_ms": result.latency_ms,
                "accepted": accepted,
                "rejected": rejected,
                "semantic_match": semantic_match,
            }
        )

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    sorted_latencies = sorted(latencies)
    p95_index = max(0, min(len(sorted_latencies) - 1, round(len(latencies) * 0.95) - 1))
    report = {
        "summary": {
            "case_count": len(cases),
            "positive_cases": positive_cases,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "write_precision": precision,
            "write_recall": recall,
            "write_f1": f1,
            "semantic_accuracy": (
                semantic_correct / positive_cases if positive_cases else 1.0
            ),
            "provider_error_rate": provider_errors / len(cases),
            "average_latency_ms": round(statistics.mean(latencies)),
            "p95_latency_ms": sorted_latencies[p95_index],
            "total_latency_ms": sum(latencies),
        },
        "cases": case_results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
