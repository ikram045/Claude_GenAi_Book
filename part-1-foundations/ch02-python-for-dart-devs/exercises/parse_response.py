"""Exercise 6 — Validate a model response with Pydantic.

This is Chapter 8 in miniature. You asked a model for JSON. You got back a
string you hope is JSON. Pydantic is the wall between that hope and the rest
of your program.

Target shape:
    {"answer": "...", "confidence": 0.87, "sources": [{"doc": "a.pdf", "page": 3}]}

Rules:
    - confidence must be between 0.0 and 1.0 inclusive
    - sources must contain at least one entry
    - page must be >= 1
"""

from pydantic import BaseModel


class Source(BaseModel):
    doc: str
    page: int


class ModelResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[Source]


def parse(raw: str) -> ModelResponse | None:
    """Parse raw JSON into a ModelResponse.

    Return None if it is invalid rather than raising — the caller wants to fall
    back gracefully, not crash. Catch `pydantic.ValidationError`.
    """
    raise NotImplementedError("your turn")
