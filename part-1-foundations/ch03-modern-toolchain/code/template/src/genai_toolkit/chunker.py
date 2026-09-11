"""Chapter 2's chunker, promoted to a properly typed package module.

The difference from the script version: full annotations that pass mypy --strict,
a module-level logger instead of prints, and a docstring that says why, not what.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chunk:
    """One window of text, with enough metadata to cite it later."""

    text: str
    source: str
    index: int
    tags: tuple[str, ...] = field(default=())

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def __repr__(self) -> str:
        preview = self.text[:40].replace("\n", " ")
        return f"Chunk({self.source}#{self.index}, {self.word_count}w, {preview!r}...)"


def chunk_text(
    text: str,
    source: str,
    size: int = 50,
    overlap: int = 10,
) -> Iterator[Chunk]:
    """Split text into overlapping word windows.

    Overlap matters: a sentence split across a boundary is recoverable if the
    windows overlap, and lost forever if they don't. Chapter 11 goes deep on this.

    Raises:
        ValueError: if overlap >= size, which would never advance.
    """
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")

    words = text.split()
    step = size - overlap
    logger.debug("chunking %d words from %s (size=%d, overlap=%d)", len(words), source, size, overlap)

    for i, start in enumerate(range(0, len(words), step)):
        window = words[start : start + size]
        if not window:
            break
        yield Chunk(text=" ".join(window), source=source, index=i)
