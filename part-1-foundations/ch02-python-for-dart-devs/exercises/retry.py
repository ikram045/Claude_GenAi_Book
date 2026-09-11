"""Exercise 4 — Async retry with exponential backoff.

You will reuse this function in every project in this book. Network calls to
model providers fail constantly: rate limits, timeouts, transient 5xx.

Backoff schedule with base_delay=0.1:
    attempt 1 fails -> wait 0.1s
    attempt 2 fails -> wait 0.2s
    attempt 3 fails -> raise

Use `await asyncio.sleep(...)`, never `time.sleep(...)`. Gotcha #13.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry(
    fn: Callable[[], Awaitable[T]],
    attempts: int = 3,
    base_delay: float = 0.1,
) -> T:
    """Call fn(), retrying on any exception with exponential backoff.

    Returns the first successful result. Re-raises the last exception if every
    attempt fails.
    """
    raise NotImplementedError("your turn")
