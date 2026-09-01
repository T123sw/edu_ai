"""Pure helpers for assessment analytics with explicit denominators."""

from __future__ import annotations

from statistics import mean, median


def ratio(numerator: int, denominator: int) -> dict[str, int | float]:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "rate": round(numerator / denominator, 4) if denominator else 0.0,
    }


def score_summary(scores: list[float]) -> tuple[float | None, float | None]:
    if not scores:
        return None, None
    return round(mean(scores), 2), round(median(scores), 2)


def score_distribution(scores: list[float]) -> list[dict[str, int | str]]:
    buckets = [("0-59", 0, 60), ("60-79", 60, 80), ("80-89", 80, 90), ("90-100", 90, 101)]
    return [
        {"label": label, "count": sum(1 for score in scores if lower <= score < upper)}
        for label, lower, upper in buckets
    ]
