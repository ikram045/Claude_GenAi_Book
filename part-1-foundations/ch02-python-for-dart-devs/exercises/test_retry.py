import time

import pytest

from retry import retry


@pytest.mark.asyncio
async def test_returns_immediately_on_success():
    calls = 0

    async def ok():
        nonlocal calls
        calls += 1
        return "done"

    assert await retry(ok) == "done"
    assert calls == 1


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("transient")
        return "done"

    assert await retry(flaky, attempts=3, base_delay=0.01) == "done"
    assert calls == 3


@pytest.mark.asyncio
async def test_reraises_after_exhausting_attempts():
    async def always_fails():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        await retry(always_fails, attempts=3, base_delay=0.01)


@pytest.mark.asyncio
async def test_backoff_is_exponential():
    async def always_fails():
        raise ConnectionError("x")

    start = time.perf_counter()
    with pytest.raises(ConnectionError):
        await retry(always_fails, attempts=3, base_delay=0.1)
    elapsed = time.perf_counter() - start

    # 0.1 + 0.2 = 0.3s of waiting
    assert 0.25 < elapsed < 0.6, f"elapsed {elapsed:.2f}s — check your backoff"
