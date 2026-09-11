"""Exercise 2 — Top N words.

Case-insensitive. Strip punctuation. Ignore stopwords.
`collections.Counter` does most of the work — find its `most_common` method.
"""

STOPWORDS = {"the", "a", "an", "and", "or", "but", "is", "are", "to", "of", "in", "it"}


def top_words(text: str, n: int = 5) -> list[tuple[str, int]]:
    """Return the n most frequent non-stopwords as (word, count), most frequent first.

    >>> top_words("the cat and the dog and the cat", n=2)
    [('cat', 2), ('dog', 1)]
    """
    raise NotImplementedError("your turn")
