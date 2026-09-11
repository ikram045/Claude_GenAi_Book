import time

import pytest

from dedupe import dedupe


def test_preserves_order():
    assert dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_empty():
    assert dedupe([]) == []


def test_no_duplicates():
    assert dedupe(["a", "b", "c"]) == ["a", "b", "c"]


def test_all_same():
    assert dedupe(["a", "a", "a"]) == ["a"]


def test_is_fast_enough():
    """An O(n^2) solution will not finish this in time."""
    items = [f"item{i % 1000}" for i in range(100_000)]
    start = time.perf_counter()
    result = dedupe(items)
    elapsed = time.perf_counter() - start

    assert len(result) == 1000
    assert elapsed < 1.0, f"took {elapsed:.2f}s — are you using a list for lookups?"
