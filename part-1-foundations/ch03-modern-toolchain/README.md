# Chapter 3 · The Modern Toolchain

### Python packaging was broken for twenty years. It isn't any more — if you know what to use.

> **Week 2 · ~22 hours · Heavy setup, heavy payoff**
>
> This is the least glamorous chapter in the book and one of the two or three most
> valuable. Everything you build for the next eight months sits on what you set up here.

---

## 3.0 · Why this chapter exists

You come from Dart, where this entire topic is a solved, invisible problem. You write a
`pubspec.yaml`, you run `pub get`, and it works. Every Dart developer on earth has the same
experience. There is one obvious tool, one obvious file format, one obvious workflow, and
nobody argues about it.

Python is not like that, and the reason is worth understanding rather than just suffering.

Python is thirty-four years old. It predates the entire idea of a language-bundled package
manager. `pip` was a community project bolted on in 2008 and only became official later.
Virtual environments were a third-party hack that got absorbed into the standard library.
Then came `easy_install`, `setuptools`, `distutils`, `eggs`, `wheels`, `requirements.txt`,
`setup.py`, `setup.cfg`, `Pipenv`, `conda`, `poetry`, `pdm`, `hatch`, and `pyproject.toml` —
each solving real problems, none fully replacing what came before.

The result was two decades of genuine misery. "Works on my machine" became an industry
joke largely because of Python. Every Python developer over thirty has a story about a
week lost to dependency resolution.

**Here is the good news, and it is recent enough that most tutorials haven't caught up:
this is now solved.** A tool called `uv`, released in 2024, does what `pub` does for Dart —
one tool, one config file, one lockfile, fast, obvious. It is written in Rust and is
roughly 10–100× faster than what came before, which matters more than it sounds when you're
iterating.

So this chapter teaches you the modern stack and largely ignores the historical one. You'll
still meet `requirements.txt` in older codebases and you'll be able to read it. But you'll
write `pyproject.toml`, and your life will look much more like the Dart life you're used
to than the Python horror stories suggest.

### What you'll have at the end

A project template you'll copy for every project in this book:

- **`uv`** — packages, virtual environments, Python versions themselves
- **`ruff`** — linting and formatting, one tool, instantaneous
- **`mypy`** — static type checking, recovering much of what Dart gave you
- **`pytest`** — testing, including async
- **`pydantic-settings`** — configuration and secrets, typed
- **`pre-commit`** — the gate that stops bad code reaching your repo
- Structured logging, a task runner, and a sane `.gitignore`

Set this up once, properly, and you stop thinking about it. That's the goal. Tooling should
be invisible, and the way it becomes invisible is by being correct from the start.

---

## 3.1 · The one concept Dart doesn't have: virtual environments

If you learn one thing in this chapter, learn this. It explains 90% of Python confusion.

### What Dart does

When you run `pub get`, Dart downloads packages into a global cache and creates a
`.dart_tool/package_config.json` mapping *this project's* package names to specific cached
versions. Two projects can depend on different versions of the same package with no
conflict. The resolution is per-project, and you never think about it.

### What Python does by default

Python installs packages into a single shared directory — `site-packages` — belonging to
the interpreter itself. There is no per-project mapping.

Follow the consequence:

```
Project A needs  httpx 0.24
Project B needs  httpx 0.27

pip install httpx==0.24     # Project A works
pip install httpx==0.27     # Project A is now broken
```

There is one `httpx` for the whole machine. Installing for one project silently breaks
another. Multiply by fifty packages across ten projects and you have the situation that
produced two decades of complaints.

### The fix: a virtual environment

A virtual environment is a **directory containing its own copy of the Python interpreter
and its own `site-packages`**. Activate it, and `python` and `pip` refer to *that* copy.
Each project gets its own, fully isolated.

```
myproject/
├── .venv/                      ← the virtual environment
│   ├── bin/python              ← this project's interpreter
│   └── lib/python3.12/site-packages/    ← this project's packages ONLY
├── pyproject.toml
└── src/
```

`.venv/` is disposable and never committed. It's a build artefact — the Python equivalent
of `.dart_tool/`. Delete it and recreate it any time.

> **The mental model:** Dart isolates packages *logically*, through a per-project mapping.
> Python isolates them *physically*, by giving each project its own interpreter directory.
> Same outcome, cruder mechanism, and it's the mechanism you must understand — because
> when something mysterious happens, the answer is almost always "you're in the wrong
> environment."

### The three questions to ask when something is broken

Ninety percent of Python environment confusion resolves to one of these:

1. **Which Python am I running?** → `which python` (Unix) — is it the one in `.venv/bin/`?
2. **Is my environment active?** → your prompt usually shows `(.venv)`
3. **Where did that package install to?** → `pip show <package>` and read the `Location:`

Memorise those three. They'll save you hours over the next year.

### Why `uv` makes this mostly disappear

Historically you managed environments by hand: `python -m venv .venv`, then
`source .venv/bin/activate`, and remembering to activate in every new shell. Forgetting was
constant, and forgetting is what causes "but I installed it!"

`uv` handles this automatically. `uv run` finds or creates the right environment and uses
it. You will rarely activate anything manually. But you now understand what it's doing on
your behalf, which is why we spent a page on it.

---

## 3.2 · Installing `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart your shell and verify:

```bash
uv --version
```

`uv` also manages **Python itself** — you don't need a system Python, and you shouldn't use
one for projects:

```bash
uv python install 3.12          # download and install Python 3.12
uv python list                  # what's available
```

> **Never use your operating system's Python for projects.** On Linux, the system Python
> belongs to your package manager, and installing into it can break OS tooling. Let `uv`
> manage project interpreters. This one rule prevents an entire category of problem.

### The `uv` command map

If you know `pub`, this table is most of what you need:

| Dart | `uv` | What it does |
|---|---|---|
| `dart create myproject` | `uv init myproject` | New project |
| `pub get` | `uv sync` | Install from the lockfile |
| `pub add http` | `uv add httpx` | Add a dependency |
| `pub add --dev test` | `uv add --dev pytest` | Add a dev dependency |
| `pub remove http` | `uv remove httpx` | Remove one |
| `pub upgrade` | `uv lock --upgrade` | Update the lockfile |
| `dart run bin/main.dart` | `uv run python -m myproject` | Run in the environment |
| `pub outdated` | `uv tree --outdated` | What's stale |
| *(no equivalent)* | `uvx ruff check .` | Run a tool without installing it |

That last one is genuinely useful — `uvx` downloads, caches and runs a CLI tool in a
throwaway environment. It's `npx` for Python.

---

## 3.3 · Creating a project

```bash
uv init --package genai-toolkit
cd genai-toolkit
```

The `--package` flag matters: it produces an installable package with a `src/` layout
rather than a loose script. That's what you want for anything real.

```
genai-toolkit/
├── .git/
├── .gitignore
├── .python-version          # pins the Python version for this project
├── README.md
├── pyproject.toml           # ← your pubspec.yaml
└── src/
    └── genai_toolkit/
        └── __init__.py
```

Note the name change: `genai-toolkit` on disk and on PyPI (hyphens), `genai_toolkit` as the
importable module (underscores — hyphens aren't legal in Python identifiers). This
convention is universal and trips people up exactly once.

### Why `src/` layout

You'll see two layouts in the wild:

```
flat/                          src/
├── myproject/                 ├── src/
│   └── __init__.py            │   └── myproject/
└── tests/                     │       └── __init__.py
                               └── tests/
```

**Use `src/`.** The reason is subtle and important: with the flat layout, your package
directory sits in the working directory, so `import myproject` picks it up *whether or not
the package is properly installed*. Your tests can pass locally and the package can still
be broken for users, because you were accidentally importing source files rather than the
installed package.

With `src/`, the only way to import your code is to install it, so your tests exercise
what your users will actually get. It catches packaging mistakes before they ship, and it
costs nothing.

---

## 3.4 · `pyproject.toml`, line by line

This is your `pubspec.yaml`. One file, all configuration — dependencies *and* tool settings.
That consolidation is the main thing `pyproject.toml` bought the ecosystem.

```toml
[project]
name = "genai-toolkit"
version = "0.1.0"
description = "Learning GenAI, one chapter at a time"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "mypy>=1.10",
    "ruff>=0.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**`[project]`** — metadata. `requires-python` is a real constraint that `uv` enforces.

**`dependencies`** — what your code needs to run. Compare to Dart's `dependencies:`.

**`[dependency-groups]`** — what *you* need to develop it: test runners, linters, type
checkers. Compare to `dev_dependencies:`. These are never installed for people who consume
your package.

**`[build-system]`** — how to turn this into an installable artefact. `hatchling` is a fine
default; you'll rarely touch this.

### Version constraints

| Spec | Means |
|---|---|
| `httpx>=0.27` | At least 0.27, any newer. Sensible default. |
| `httpx>=0.27,<0.28` | Pinned to a minor range |
| `httpx~=0.27.0` | "Compatible release" — `>=0.27.0, <0.28.0` |
| `httpx==0.27.2` | Exactly this. Use sparingly. |

> **Constrain loosely in `pyproject.toml`, pin exactly in the lockfile.** This is the same
> philosophy as `pubspec.yaml` versus `pubspec.lock`, and the reasoning is identical: the
> manifest expresses what you're *compatible with*, and the lockfile records what you
> actually *tested against*.

---

## 3.5 · Adding dependencies, and the lockfile

```bash
uv add httpx pydantic pydantic-settings
uv add --dev pytest pytest-asyncio pytest-cov mypy ruff
```

Each command updates `pyproject.toml`, resolves the full dependency graph, writes
`uv.lock`, and syncs `.venv/`. It's fast enough — usually well under a second — that you
stop thinking about it.

### The lockfile

`uv.lock` records the **exact** version and hash of every package in the resolved graph,
including transitive dependencies you never named. Your `pubspec.lock`.

```bash
uv sync                  # install exactly what the lockfile says
uv lock --upgrade        # re-resolve, allowing newer versions
uv lock --upgrade-package httpx    # upgrade just one
```

> **Commit `uv.lock`. Never commit `.venv/`.**
>
> The lockfile is how "works on my machine" becomes "works on every machine." Without it,
> you and CI and your colleague each resolve dependencies independently, at different
> times, and get different graphs. A transitive dependency ships a breaking change on a
> Tuesday and your CI fails on code you didn't touch. With a lockfile, that can't happen —
> everyone installs byte-identical packages until someone deliberately runs `uv lock
> --upgrade`.

### Running things

```bash
uv run python src/genai_toolkit/main.py
uv run pytest
uv run ruff check .
uv run mypy src/
```

`uv run` guarantees the environment exists, is synced with the lockfile, and is active for
that command. No activation, nothing to forget. If you prefer the traditional way it still
works:

```bash
source .venv/bin/activate        # then plain `python`, `pytest`, etc.
deactivate
```

But `uv run` is better, because it's stateless — it can't be wrong.

---

## 3.6 · Ruff — linting and formatting

`ruff` replaces roughly eight tools that used to be separate: `black` (formatting),
`flake8` (linting), `isort` (import sorting), `pyupgrade`, `pydocstyle`, `bandit` and
others. One tool, one config, written in Rust, and fast enough to run on save without
noticing.

Your `dart format` and `dart analyze`, combined.

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes — unused imports, undefined names
    "I",      # isort — import ordering
    "B",      # flake8-bugbear — real bug patterns
    "C4",     # comprehension simplifications
    "UP",     # pyupgrade — modernise syntax
    "ARG",    # unused arguments
    "SIM",    # simplifiable code
    "TCH",    # type-checking imports
    "PTH",    # use pathlib, not os.path
    "RUF",    # ruff's own rules
]
ignore = [
    "E501",   # line length — the formatter handles this
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ARG", "S101"]     # asserts and unused fixtures are fine in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

Usage:

```bash
uv run ruff check .              # lint
uv run ruff check --fix .        # lint and auto-fix what it can
uv run ruff format .             # format
uv run ruff format --check .     # verify formatting without changing (for CI)
```

### The rules worth knowing about

`B` (bugbear) is the one that earns its place — it catches real bugs, including two from
Chapter 2:

```python
def f(items=[]):        # B006: mutable default argument
    ...

fs = [lambda: i for i in range(3)]     # B023: function uses loop variable
```

Both of those are traps you read about yesterday, now caught automatically. This is why
linters are worth configuring properly rather than accepting defaults.

`SIM` will nag you into idiomatic Python, which is exactly what you want while the idioms
are still new:

```python
if x == True:           # SIM201 → if x:
if len(items) == 0:     # → if not items:
```

`PTH` pushes you toward `pathlib` over `os.path`, which is the right default and one you'd
otherwise have to remember.

---

## 3.7 · mypy — getting Dart's safety back

This is the section you'll appreciate most. Chapter 2 told you type hints do nothing at
runtime. `mypy` is the thing that makes them mean something.

```toml
[tool.mypy]
python_version = "3.12"
files = ["src", "tests"]
strict = true

# strict = true turns on all of the below; listed here so you know what it means
# warn_return_any = true
# warn_unused_configs = true
# disallow_untyped_defs = true
# disallow_incomplete_defs = true
# check_untyped_defs = true
# disallow_untyped_decorators = true
# no_implicit_optional = true
# warn_redundant_casts = true
# warn_unused_ignores = true
# warn_no_return = true
# warn_unreachable = true

[[tool.mypy.overrides]]
module = ["some_untyped_library.*"]
ignore_missing_imports = true
```

```bash
uv run mypy src/
```

### Start strict

Most Python projects adopt mypy gradually and end up permanently half-typed, because
tightening later means fixing hundreds of errors at once and nobody ever schedules that.

**Start with `strict = true` on day one.** You're starting from zero code, so strictness
costs nothing now and is nearly impossible to retrofit. Coming from Dart's sound null
safety, strict mypy will feel familiar rather than oppressive.

What it catches:

```python
def greet(name: str) -> str:
    return f"Hello {name}"

greet(42)
# error: Argument 1 to "greet" has incompatible type "int"; expected "str"

def find(x: int) -> str | None: ...

result = find(1)
print(result.upper())
# error: Item "None" of "str | None" has no attribute "upper"
```

That second one is precisely the null-safety check Dart gives you at compile time. You had
it, you lost it in Chapter 2, and here it is back — as long as you actually run mypy, which
is what pre-commit and CI are for.

### The escape hatch, and using it honestly

```python
result = some_untyped_lib.call()  # type: ignore[no-any-return]
```

Always narrow the ignore to a specific error code, never a bare `# type: ignore`. A bare
ignore silences everything on that line forever, including errors introduced later. With
`warn_unused_ignores = true`, mypy will also tell you when an ignore has become unnecessary
— which keeps them from accumulating as fossils.

---

## 3.8 · pytest

Your `package:test`, but more powerful and, once you learn fixtures, genuinely pleasant.

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--strict-markers",
    "--cov=src",
    "--cov-report=term-missing",
]
markers = [
    "slow: deselect with -m 'not slow'",
    "integration: requires network or external services",
]
```

### Tests are plain functions

No class, no boilerplate, no `expect()`. Just `assert`.

```python
# tests/test_chunker.py
from genai_toolkit.chunker import chunk_text


def test_respects_size() -> None:
    chunks = list(chunk_text("a b c d e f", source="x", size=2, overlap=0))
    assert len(chunks) == 3
    assert chunks[0].text == "a b"
```

pytest rewrites the `assert` statement so failures show you the actual values, which is why
it doesn't need an assertion library:

```
E       assert 4 == 3
E        +  where 4 = len([Chunk(...), Chunk(...), Chunk(...), Chunk(...)])
```

### Parametrize — one test, many cases

The feature you'll use most:

```python
import pytest


@pytest.mark.parametrize(
    ("size", "overlap", "expected"),
    [
        (2, 0, 3),
        (3, 0, 2),
        (3, 1, 3),
        (10, 0, 1),
    ],
)
def test_chunk_counts(size: int, overlap: int, expected: int) -> None:
    chunks = list(chunk_text("a b c d e f", source="x", size=size, overlap=overlap))
    assert len(chunks) == expected
```

That's four separate tests with four separate names in the output, from one function. When
one fails you see exactly which parameters broke it.

### Fixtures — setup, teardown, and dependency injection

Fixtures are pytest's best idea. A fixture is a function that produces a value; tests
request it by naming it as a parameter.

```python
# tests/conftest.py — fixtures here are available to every test file
import pytest
from pathlib import Path


@pytest.fixture
def sample_doc(tmp_path: Path) -> Path:
    """A throwaway document. tmp_path is a built-in fixture giving a temp dir."""
    doc = tmp_path / "sample.txt"
    doc.write_text("the quick brown fox jumps over the lazy dog")
    return doc


@pytest.fixture
def chunker() -> Chunker:
    return Chunker(size=5, overlap=1)


def test_reads_document(sample_doc: Path, chunker: Chunker) -> None:
    chunks = chunker.process(sample_doc)     # both fixtures injected by name
    assert len(chunks) > 0
```

This is dependency injection, and you already know why it's good. Setup and teardown in one
place:

```python
@pytest.fixture
def db():
    conn = connect()
    yield conn            # the test runs here
    conn.close()          # teardown, guaranteed even if the test fails
```

Scope controls how often a fixture is rebuilt — `function` (default), `module`, `session`:

```python
@pytest.fixture(scope="session")
def embedding_model():
    """Expensive. Load once for the entire test run."""
    return load_model()
```

You'll want that one badly in Part III.

### Async tests

With `asyncio_mode = "auto"` set, async tests just work:

```python
async def test_retry_succeeds_eventually() -> None:
    result = await retry(flaky_operation, attempts=3)
    assert result == "done"
```

### Testing that something raises

```python
def test_rejects_bad_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        list(chunk_text("a b", source="x", size=2, overlap=5))
```

### Useful invocations

```bash
uv run pytest                          # everything
uv run pytest tests/test_chunker.py    # one file
uv run pytest -k "overlap"             # tests whose name matches
uv run pytest -m "not slow"            # deselect a marker
uv run pytest -x                       # stop at first failure
uv run pytest --lf                     # rerun only last-failed
uv run pytest -s                       # don't capture stdout (see your prints)
uv run pytest --cov=src --cov-report=html   # coverage report you can browse
```

`--lf` is the one that changes your workflow. Fix, rerun only what failed, repeat.

> **On coverage:** it measures which lines ran, not whether they were tested *well*. 100%
> coverage with weak assertions is worse than 70% with sharp ones, because it produces
> false confidence. Use it to find code nobody exercises at all — that's a real signal —
> and ignore the headline percentage.

---

## 3.9 · Configuration and secrets

You're about to have API keys. Here's how to handle them so you never commit one.

> **Before anything else:** a leaked API key is a real, expensive incident. Keys have been
> scraped from public GitHub repos within *minutes* of being pushed. Get this right now,
> while your keys are worthless, so the habit is automatic when they aren't.

### The layers

1. **`.env`** — a local file of key-value pairs. **Never committed.**
2. **`.env.example`** — the same keys with dummy values. **Committed**, so a new contributor
   knows what's needed.
3. **`pydantic-settings`** — loads and *validates* them into a typed object.

```bash
uv add pydantic-settings
```

```python
# src/genai_toolkit/config.py
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment or .env.

    Values are validated on load, so a misconfigured app fails at startup with a
    clear message rather than at 3am with a confusing one.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(min_length=10)
    model: str = "claude-opus-5"
    max_tokens: int = Field(default=16_000, ge=1, le=200_000)
    log_level: str = "INFO"
    request_timeout: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Cached so the file is read once per process."""
    return Settings()
```

```bash
# .env  — NEVER commit this
ANTHROPIC_API_KEY=sk-ant-your-real-key
LOG_LEVEL=DEBUG
```

```bash
# .env.example  — DO commit this
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
MODEL=claude-opus-5
MAX_TOKENS=16000
LOG_LEVEL=INFO
```

Field names map to environment variables case-insensitively, so `anthropic_api_key` reads
`ANTHROPIC_API_KEY`. Usage:

```python
settings = get_settings()
client = Anthropic(api_key=settings.anthropic_api_key)
```

**Why this rather than `os.environ["ANTHROPIC_API_KEY"]`:** a missing or malformed key
fails at startup with a precise message naming the field, instead of producing a `KeyError`
somewhere deep in a request handler, or — worse — a string `"None"` being sent to an API.
Validating configuration at the boundary is the same instinct as validating model output
with Pydantic, and it's the same tool.

### The rules

1. `.env` is in `.gitignore`. Always. Check it right now.
2. Never `print()` or log a settings object — it may contain the key. Use
   `SecretStr` for real deployments; it redacts in `repr`.
3. If you leak a key, **rotate it immediately**. Don't delete the commit and hope. Git
   history is forever, and scrapers are fast.

---

## 3.10 · Logging, not `print`

`print` is fine while exploring. In anything that runs unattended, use `logging` — because
you need levels, timestamps, module names, and the ability to turn detail up in production
without redeploying.

```python
# src/genai_toolkit/logging_config.py
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    # Third-party libraries are chatty. Quiet them.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

```python
import logging

logger = logging.getLogger(__name__)      # module-level, named after the module


def search(query: str) -> list[str]:
    logger.debug("searching for %r", query)
    results = do_search(query)
    logger.info("found %d results for %r", len(results), query)
    if not results:
        logger.warning("no results for %r", query)
    return results
```

Two conventions worth adopting immediately:

**Use `%s` placeholders, not f-strings.** `logger.debug("searching %r", query)` only formats
the string if DEBUG is enabled. `logger.debug(f"searching {query}")` formats it every time,
even when it's discarded. On a hot path with expensive `repr`s, that's real waste.

**Name loggers `__name__`.** You get a hierarchy matching your package structure, so you can
turn up logging for one module without drowning in everything else.

Levels, and when to use them:

| Level | Use for |
|---|---|
| `DEBUG` | Detail for diagnosis. Prompt contents, chunk scores, token counts |
| `INFO` | Normal significant events. "Indexed 1,200 chunks" |
| `WARNING` | Unexpected but handled. Retry, fallback, empty result |
| `ERROR` | A real failure, with a stack trace |
| `CRITICAL` | The process cannot continue |

In Chapter 23 this becomes structured tracing, which is how you debug non-deterministic
systems. What you set up here is the foundation for that.

---

## 3.11 · pre-commit — the gate

Linters only help if they run. `pre-commit` runs them automatically before each commit, so
broken code can't get in.

```bash
uv add --dev pre-commit
uv run pre-commit install        # installs the git hook — do this once per clone
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-requests]
```

Now `git commit` runs ruff, formats your files, checks types, and blocks obvious mistakes.
`detect-private-key` and `check-added-large-files` have saved more repositories than any
amount of discipline.

```bash
uv run pre-commit run --all-files      # run over everything, not just staged
```

It will feel obstructive for about three days, then it becomes the thing that lets you stop
worrying. Commit with `--no-verify` only when you genuinely mean it.

---

## 3.12 · A task runner

Nobody remembers the flags. Put them in a `Makefile` and stop thinking.

```makefile
.PHONY: help install fmt lint type test check clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Sync the environment and install git hooks
	uv sync
	uv run pre-commit install

fmt:  ## Format the code
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Lint without changing anything
	uv run ruff check .
	uv run ruff format --check .

type:  ## Type check
	uv run mypy src tests

test:  ## Run the tests
	uv run pytest

check: lint type test  ## Everything CI runs

clean:  ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist
	find . -type d -name __pycache__ -exec rm -rf {} +
```

`make check` before every push. `make help` lists the targets.

---

## 3.13 · `.gitignore`

```gitignore
# Environments
.venv/
venv/
.env
.env.*
!.env.example

# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Tooling caches
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# Editors
.vscode/
.idea/
*.swp
.DS_Store

# Data — add your own; these get large and are rarely reviewable
*.sqlite3
data/raw/
*.faiss
```

The `.env` / `!.env.example` pair is doing important work: ignore every env file, but keep
the example. Verify it with `git check-ignore -v .env` — if that prints a rule, you're
protected.

---

## 3.14 · Continuous integration

One file, and now every push is checked on a clean machine — which catches the "works on my
machine" problems your lockfile didn't.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-extras --dev

      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .

      - name: Type check
        run: uv run mypy src tests

      - name: Test
        run: uv run pytest --cov=src --cov-report=term-missing
```

Set this up now, on a project with four files, while it takes ten minutes. In Chapter 22
you'll add an eval job to this same pipeline, and that is the thing that makes you
employable — a CI run that blocks a prompt change from shipping if quality regresses.

---

## 3.15 · Build it: the template

Assemble the whole thing. You'll copy this for every project in this book, so build it
carefully once.

```bash
uv init --package genai-toolkit
cd genai-toolkit

uv add httpx pydantic pydantic-settings
uv add --dev pytest pytest-asyncio pytest-cov mypy ruff pre-commit
```

Target structure:

```
genai-toolkit/
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
├── .gitignore
├── .env.example
├── .python-version
├── Makefile
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── genai_toolkit/
│       ├── __init__.py
│       ├── config.py
│       ├── logging_config.py
│       └── chunker.py          ← port Chapter 2's chunker here, typed strictly
└── tests/
    ├── conftest.py
    ├── test_config.py
    └── test_chunker.py
```

Then move Chapter 2's `chunker.py` into `src/genai_toolkit/`, add full type annotations,
and write real tests for it. This is the exercise: taking a script and making it a package.

**You're done when `make check` passes with zero errors** — ruff clean, mypy strict clean,
all tests green.

### The things that will go wrong, and what they mean

Expect at least three of these. They're the standard rites of passage:

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: genai_toolkit` in tests | Package not installed into the venv | `uv sync` — with `src/` layout it must be installed |
| mypy: `Function is missing a type annotation` | `strict = true` doing its job | Annotate it. That's the point |
| mypy: `Cannot find implementation for module X` | Library ships no type stubs | Add an `ignore_missing_imports` override |
| `pytest` finds no tests | Files not named `test_*.py`, or `testpaths` wrong | Check both |
| Async test skipped with a warning | `asyncio_mode` not set | Set `asyncio_mode = "auto"` |
| pre-commit rewrites files, commit fails | Formatter changed things | `git add` the changes and commit again — normal |
| `.env` shows in `git status` | `.gitignore` missing or wrong | Fix it *now*, before any key exists |

---

## 3.16 · Exercises

**1 · Break the environment on purpose.** Delete `.venv/` entirely. Run `uv run pytest`.
Watch it rebuild from the lockfile. Now you know the environment is disposable, which
removes most of the fear around it.

**2 · Prove the lockfile works.** Clone your repo into a second directory, run `uv sync`,
and confirm identical package versions with `uv pip list`. This is the guarantee you're
relying on.

**3 · Make mypy shout at you.** Write a function annotated `-> str` that returns `None` on
some path. Run mypy. Read the error carefully. Fix it by changing the annotation to
`str | None`, then watch mypy flag every caller that doesn't handle the `None`. **This is
Dart's null safety, reconstructed.**

**4 · Write a fixture with teardown.** A fixture that creates a temp file, yields its path,
and deletes it after. Prove the teardown runs even when the test fails — make the test fail
deliberately and check.

**5 · Parametrize something real.** Convert three near-identical tests into one
parametrized test with three cases. Note that failure output still names which case broke.

**6 · Get caught by pre-commit.** Commit a file with a trailing whitespace, an unused
import, and a line `API_KEY = "sk-ant-abc123..."`. Watch which hooks catch which. Fix and
commit properly.

**7 · Configure a required setting.** Add a required field to `Settings` with no default.
Run the app without it in `.env`. Read the error. Notice it names the exact field — that's
the payoff over `os.environ`.

**8 · Turn logging up.** Add `DEBUG` logs to the chunker. Run with `LOG_LEVEL=INFO`, then
`LOG_LEVEL=DEBUG`. Then silence `httpx` and confirm it went quiet.

---

## 3.17 · Checkpoint

> **Move on to Chapter 4 when all of these are true.**

**Explain, out loud, without looking:**

1. What a virtual environment is and what problem it solves that Dart never had.
2. Why you commit `uv.lock` but never `.venv/`.
3. Why `src/` layout is safer than a flat layout.
4. The difference between `dependencies` and `[dependency-groups] dev`.
5. Why `logger.debug("x %s", val)` is preferable to `logger.debug(f"x {val}")`.

**Do, from memory:**

6. Create a new project with `uv`, add one runtime and one dev dependency.
7. Write a parametrized test with four cases.
8. Write a fixture with teardown and use it in two tests.
9. Configure mypy in strict mode and make a real project pass it.

**Verify:**

10. `make check` passes: ruff clean, mypy strict clean, tests green.
11. `git check-ignore -v .env` confirms your `.env` is ignored.
12. CI is green on GitHub.
13. You can delete `.venv/` and be fully working again in one command.

Number 13 is the one that tells you you've understood. If deleting `.venv/` makes you
nervous, re-read section 3.1.

---

## 3.18 · Going deeper (optional)

**The `uv` documentation** is unusually good and short enough to read in an evening. Worth
it — you'll use this tool daily for years.

**If you want the history:** search for "Python packaging" and PEP 517, 518 and 621. You'll
see the twenty-year argument that produced `pyproject.toml`. It's genuinely interesting as
a case study in how ecosystems evolve without central authority, and it makes the current
state feel like an achievement rather than an inconvenience.

**Ruff's rule list** is worth skimming once — hundreds of rules, each documented with an
example of the bug it prevents. It's a free education in Python failure modes, and reading
twenty of them will teach you idioms you'd otherwise take a year to absorb.

**If you want to go further on testing:** look up `hypothesis`, which generates test inputs
to find edge cases you wouldn't think of. Overkill for now, excellent for parsing and
chunking logic in Part III.

---

<div align="center">

**[← Chapter 2](../ch02-python-for-dart-devs/)** · **[The Book](../../readme.md)** · **[Chapter 4 → Async & FastAPI](../ch04-async-and-fastapi/)**

*Chapter 3 of 31 · Week 2*

</div>
