"""Exercise 5 — An async generator that streams words.

This is a streaming LLM response with the model removed. The shape you build
here is exactly the shape of Chapter 6's token streaming.
"""

from collections.abc import AsyncIterator


async def stream_words(text: str, delay: float = 0.05) -> AsyncIterator[str]:
    """Yield each word of `text`, pausing `delay` seconds between them.

    Use `await asyncio.sleep(delay)`.
    """
    raise NotImplementedError("your turn")


async def collect(stream: AsyncIterator[str]) -> list[str]:
    """Consume an async iterator into a list. Use `async for`."""
    raise NotImplementedError("your turn")
