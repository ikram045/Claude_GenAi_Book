# genai-toolkit — the Chapter 3 template

The reference implementation of the project setup from Chapter 3.

**Build your own version first.** Then diff against this one. Reading it before you've
struggled with it converts an exercise into a tutorial, and you'll learn a fraction as much.

## Setup

```bash
uv sync
uv run pre-commit install
cp .env.example .env      # then add a real key
```

## Daily use

```bash
make check     # lint + types + tests — run before every push
make fmt       # format
make test      # tests only
make help      # list targets
```

## What to look at, and why

| File | Why it's here |
|---|---|
| `pyproject.toml` | Dependencies *and* every tool's config in one file |
| `src/` layout | Forces tests to exercise the installed package, not loose source |
| `config.py` | Typed, validated settings — fails at startup, not at 3am |
| `logging_config.py` | `%s` placeholders, `__name__` loggers, noisy libraries silenced |
| `chunker.py` | Chapter 2's script, promoted to a strict-typed module |
| `tests/conftest.py` | Fixtures shared across test files |
| `tests/test_chunker.py` | Parametrize, `pytest.raises`, fixtures — the patterns you'll reuse |
| `.pre-commit-config.yaml` | The gate. `detect-private-key` alone earns its keep |
| `.github/workflows/ci.yml` | Chapter 22 adds an eval job to this exact file |

## Verify your setup

```bash
rm -rf .venv && uv run pytest     # rebuilds from the lockfile and passes
git check-ignore -v .env          # prints a rule = your key is safe
```

If deleting `.venv/` makes you nervous, re-read section 3.1.
