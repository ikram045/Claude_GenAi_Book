"""Exercise 3 — Walk a dotted path through nested dicts.

Write it TWICE: once checking before each step (LBYL), once letting it fail
and catching (EAFP). Keep both. Then decide which you'd rather maintain.
"""

from typing import Any


def safe_get_lbyl(data: dict, path: str, default: Any = None) -> Any:
    """Look Before You Leap — check each step exists before descending.

    >>> safe_get_lbyl({"user": {"name": "Ada"}}, "user.name")
    'Ada'
    >>> safe_get_lbyl({"user": {}}, "user.name", "unknown")
    'unknown'
    """
    raise NotImplementedError("your turn")


def safe_get_eafp(data: dict, path: str, default: Any = None) -> Any:
    """Easier to Ask Forgiveness — just descend, catch what goes wrong.

    Which exceptions can this raise? There are at least three.
    """
    raise NotImplementedError("your turn")
