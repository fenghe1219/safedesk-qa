from __future__ import annotations

from collections.abc import Iterable


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def recall_at_k(retrieved: list[str], expected: list[str], *, k: int | None = None) -> float:
    if not expected:
        return 1.0
    window = retrieved if k is None else retrieved[:k]
    return safe_div(sum(1 for title in expected if title in window), len(expected))


def reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for index, title in enumerate(retrieved, start=1):
        if title in expected_set:
            return 1.0 / index
    return 0.0


def ratio(passed: int, total: int) -> float:
    return safe_div(passed, total)

