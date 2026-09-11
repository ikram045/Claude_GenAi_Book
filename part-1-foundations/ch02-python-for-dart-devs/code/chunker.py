"""A tiny document chunker — the ancestor of what you'll build in Chapter 11.

Run it:  python code/chunker.py

Then break it. See section 2.21 of the chapter for the five ways.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
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


def chunk_text(text: str, source: str, size: int = 50, overlap: int = 10) -> Iterator[Chunk]:
    """Split text into overlapping word windows.

    Overlap matters: a sentence split across a boundary is recoverable if the
    windows overlap, and lost forever if they don't. Chapter 11 goes deep on this.
    """
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")

    words = text.split()
    step = size - overlap

    for i, start in enumerate(range(0, len(words), step)):
        window = words[start : start + size]
        if not window:
            break
        yield Chunk(text=" ".join(window), source=source, index=i)


def main() -> None:
    sample = Path(__file__).parent / "sample.txt"
    if not sample.exists():
        sample.write_text(" ".join(f"word{i}" for i in range(200)))

    chunks = list(chunk_text(sample.read_text(), source=sample.name))

    print(f"{len(chunks)=}")
    for c in chunks[:3]:
        print(" ", c)

    total = sum(c.word_count for c in chunks)
    longest = max(chunks, key=lambda c: c.word_count)
    print(f"{total=} {longest.index=}")


if __name__ == "__main__":
    main()
