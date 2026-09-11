from pathlib import Path

import pytest

from genai_toolkit.chunker import Chunk, chunk_text


def test_splits_into_expected_windows(words: str) -> None:
    chunks = list(chunk_text(words, source="x", size=2, overlap=0))
    assert len(chunks) == 3
    assert chunks[0].text == "a b"
    assert chunks[-1].text == "e f"


@pytest.mark.parametrize(
    ("size", "overlap", "expected"),
    [
        (2, 0, 3),
        (3, 0, 2),
        (3, 1, 3),
        (10, 0, 1),
    ],
)
def test_chunk_counts(words: str, size: int, overlap: int, expected: int) -> None:
    """One test, four cases. Failure output names which case broke."""
    assert len(list(chunk_text(words, source="x", size=size, overlap=overlap))) == expected


def test_overlap_actually_overlaps(words: str) -> None:
    chunks = list(chunk_text(words, source="x", size=3, overlap=1))
    assert chunks[0].text.split()[-1] == chunks[1].text.split()[0]


def test_rejects_overlap_larger_than_size() -> None:
    with pytest.raises(ValueError, match="overlap"):
        list(chunk_text("a b", source="x", size=2, overlap=5))


def test_empty_text_yields_nothing() -> None:
    assert list(chunk_text("", source="x")) == []


def test_is_lazy() -> None:
    """A generator does no work until iterated — including the guard? No:
    the guard runs on first next(), not at call time. Worth knowing."""
    gen = chunk_text("a b", source="x", size=2, overlap=5)
    with pytest.raises(ValueError):
        next(gen)


def test_chunk_is_frozen() -> None:
    c = Chunk(text="hi", source="x", index=0)
    with pytest.raises(Exception):  # FrozenInstanceError
        c.text = "bye"  # type: ignore[misc]


def test_reads_a_real_file(sample_doc: Path) -> None:
    chunks = list(chunk_text(sample_doc.read_text(), source=sample_doc.name, size=4, overlap=1))
    assert all(c.source == "sample.txt" for c in chunks)
    assert sum(c.word_count for c in chunks) >= 9
