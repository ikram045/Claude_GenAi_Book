# Chapter 2 · Exercises

Six exercises. Each has a stub file and a test file. Your job: make the tests pass.

## Running the tests

You don't have a proper toolchain yet — that's Chapter 3. For now:

```bash
pip install pytest pytest-asyncio pydantic
pytest exercises/ -v
```

Run a single exercise while working on it:

```bash
pytest exercises/test_dedupe.py -v
```

## The rules

1. **Don't look at the solutions until your tests pass.** Solutions are in
   `solutions/`, and reading them early converts an exercise into a tutorial.
2. **Make it work, then make it idiomatic.** Get green first. Then ask: would a
   Python native have written it this way?
3. **Read the test file first.** It's the specification, and reading tests to
   understand requirements is itself a skill worth practising.

## The exercises

| # | File | Teaches |
|:---:|---|---|
| 1 | `dedupe.py` | Sets vs lists, algorithmic complexity |
| 2 | `word_frequency.py` | `Counter`, string methods, comprehensions |
| 3 | `safe_get.py` | EAFP vs LBYL, nested data |
| 4 | `retry.py` | Async, exponential backoff — **you'll reuse this all book** |
| 5 | `stream_words.py` | Async generators — a streaming LLM response, simplified |
| 6 | `parse_response.py` | Pydantic validation — Chapter 8 in miniature |
