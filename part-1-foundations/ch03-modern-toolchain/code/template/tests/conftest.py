"""Fixtures available to every test in this directory and below."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_doc(tmp_path: Path) -> Path:
    """A throwaway document. `tmp_path` is a built-in fixture giving a temp dir
    that pytest cleans up for us."""
    doc = tmp_path / "sample.txt"
    doc.write_text("the quick brown fox jumps over the lazy dog")
    return doc


@pytest.fixture
def words() -> str:
    return "a b c d e f"
