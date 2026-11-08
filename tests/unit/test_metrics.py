from __future__ import annotations

import pytest

from qa.metrics import mean, ratio, recall_at_k, reciprocal_rank, safe_div

pytestmark = pytest.mark.unit


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "b", "c"], ["a"]) == 1.0
    assert recall_at_k(["a", "b", "c"], ["a", "c"]) == 1.0
    assert recall_at_k(["a", "b", "c"], ["d"]) == 0.0
    assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0
    assert recall_at_k(["a", "b", "c"], [], k=2) == 1.0


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["a", "b"], ["a"]) == 1.0
    assert reciprocal_rank(["a", "b"], ["b"]) == 0.5
    assert reciprocal_rank([], ["b"]) == 0.0


def test_safe_aggregations() -> None:
    assert safe_div(1, 0) == 0.0
    assert ratio(1, 4) == 0.25
    assert mean([1, 2, 3]) == 2.0
    assert mean([]) == 0.0

