import time

import pytest

from stream_words import collect, stream_words


@pytest.mark.asyncio
async def test_yields_each_word():
    assert await collect(stream_words("hello async world", delay=0)) == [
        "hello",
        "async",
        "world",
    ]


@pytest.mark.asyncio
async def test_empty_text():
    assert await collect(stream_words("", delay=0)) == []


@pytest.mark.asyncio
async def test_actually_delays():
    start = time.perf_counter()
    await collect(stream_words("a b c", delay=0.05))
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.1, "did you await asyncio.sleep?"


@pytest.mark.asyncio
async def test_is_lazy_not_a_list():
    """A real stream yields as it goes — you can stop early."""
    seen = []
    async for word in stream_words("a b c d e", delay=0):
        seen.append(word)
        if len(seen) == 2:
            break
    assert seen == ["a", "b"]
