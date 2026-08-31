from __future__ import annotations

from collections.abc import Iterable


def normalize_range(
    start_ms: int,
    end_ms: int,
    *,
    total_ms: int,
) -> tuple[int, int] | None:
    total = max(0, int(total_ms))
    start = max(0, min(int(start_ms), total))
    end = max(0, min(int(end_ms), total))
    return (start, end) if end > start else None


def merge_covered_ranges(
    ranges: Iterable[tuple[int, int]],
    *,
    total_ms: int,
) -> list[tuple[int, int]]:
    normalized = sorted(
        item
        for raw in ranges
        if (item := normalize_range(*raw, total_ms=total_ms)) is not None
    )
    merged: list[tuple[int, int]] = []
    for start, end in normalized:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def covered_duration_ms(ranges: Iterable[tuple[int, int]]) -> int:
    return sum(max(0, int(end) - int(start)) for start, end in ranges)


def coverage_percent(covered_ms: int, total_ms: int) -> float:
    if total_ms <= 0:
        return 0.0
    return min(100.0, max(0.0, covered_ms / total_ms * 100.0))

