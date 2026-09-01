from __future__ import annotations

from app.resource_learning.intervals import (
    coverage_percent,
    covered_duration_ms,
    merge_covered_ranges,
    normalize_range,
)


def test_merge_ranges_deduplicates_replays_and_clamps_to_scene() -> None:
    merged = merge_covered_ranges(
        [(0, 20_000), (15_000, 35_000), (50_000, 65_000)],
        total_ms=60_000,
    )

    assert merged == [(0, 35_000), (50_000, 60_000)]
    assert covered_duration_ms(merged) == 45_000


def test_normalize_range_rejects_empty_and_reversed_ranges() -> None:
    assert normalize_range(-100, 1_000, total_ms=500) == (0, 500)
    assert normalize_range(200, 200, total_ms=500) is None
    assert normalize_range(400, 100, total_ms=500) is None


def test_merge_ranges_joins_touching_boundaries_and_ignores_invalid_ranges() -> None:
    merged = merge_covered_ranges(
        [(30, 40), (0, 10), (10, 20), (25, 25), (80, 70)],
        total_ms=100,
    )

    assert merged == [(0, 20), (30, 40)]


def test_coverage_percent_has_an_exact_eighty_percent_boundary() -> None:
    assert coverage_percent(80_000, 100_000) == 80.0
    assert coverage_percent(79_999, 100_000) < 80.0
    assert coverage_percent(120_000, 100_000) == 100.0
    assert coverage_percent(1, 0) == 0.0
