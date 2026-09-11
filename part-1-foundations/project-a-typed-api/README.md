# 🔨 Project A · The Document Service

### Week 4 · ~22 hours · The first thing you'd show a senior engineer

---

## The brief

Build a **document ingestion and chunking service**: an HTTP API that accepts documents,
splits them into retrievable chunks, stores them, and serves them back with statistics.

No AI. Not one model call. That's deliberate.

This project exists to prove one thing: **that you write Python like a professional, not
like someone who did a tutorial.** Types, tests, structure, error handling, containers, CI.
The unglamorous things that a hiring manager scans for in the first ninety seconds of
reading your code, and that most self-taught candidates simply don't have.

It is also not throwaway work. This service is the **ingestion layer of Project C**, your
production RAG system in week 15. You are building the foundation of your flagship project
now, while the only hard part is the engineering.

---

## Why this project and not something flashier

You could build a chatbot this week. Many people in your position do, and it's a mistake,
for three reasons:

1. **You don't yet know enough to build a good one.** You'd build a bad one, and bad first
   projects are hard to unlearn — you carry their bad habits into the good projects.
2. **Chatbots hide your engineering.** A reviewer sees the model output, not your code
   quality. This project has nowhere to hide: it is *entirely* your engineering.
3. **Every AI system needs this layer.** Ingestion, chunking and storage are the unglamorous
   base of every RAG system on earth. Building it properly now means that in week 15, when
   retrieval gets genuinely hard, this part is already solid and tested.

---

## Requirements

### Core API

| Method | Path | Behaviour |
|---|---|---|
| `GET` | `/health` | Liveness. Returns status and version. |
| `POST` | `/documents` | Accept a document, chunk it, store it, return metadata |
| `GET` | `/documents` | List documents, paginated |
| `GET` | `/documents/{id}` | One document's metadata |
| `GET` | `/documents/{id}/chunks` | That document's chunks, paginated |
| `DELETE` | `/documents/{id}` | Remove a document and its chunks |
| `POST` | `/chunk` | Stateless: chunk text, return chunks, store nothing |
| `GET` | `/stats` | Corpus-wide statistics |
| `POST` | `/documents/{id}/reprocess` | Re-chunk with new parameters, streaming progress via SSE |

### Functional requirements

**1 · Ingestion**
- Accept raw text in a JSON body, and file upload (`.txt`, `.md`) via `multipart/form-data`.
- Reject files over a configurable size limit with a clear 413.
- Reject unsupported content types with a clear 415.
- Store a content hash; ingesting the same content twice returns the existing document
  rather than duplicating it.

**2 · Chunking**
- Configurable `size` and `overlap` per request, with validated bounds.
- Chunks carry: text, index, source document, character offsets, word count.
- Character offsets matter — in Part III you'll need to cite exact source positions.

**3 · Storage**
- SQLite via `aiosqlite`, or in-memory behind a `Protocol` with a swappable implementation.
- Whichever you choose, **the storage layer must be behind an interface**, because Chapter
  12 replaces it with a vector database. Design for that now.

**4 · Streaming**
- `/documents/{id}/reprocess` streams progress as SSE: chunks completed, percentage, then a
  final summary event.
- Handle client disconnect: stop work, log it.

**5 · Observability**
- Structured logging with a request ID on every line.
- `X-Request-ID` and `X-Process-Time` on every response.

**6 · Configuration**
- All settings via `pydantic-settings`. No magic numbers in code.
- `.env.example` committed; `.env` never committed.

### Quality bar — this is the actual point of the project

| Requirement | Verified by |
|---|---|
| `mypy --strict` passes, zero `# type: ignore` without a written reason | `make type` |
| `ruff check` and `ruff format --check` pass | `make lint` |
| Test coverage ≥ 85%, with **meaningful** assertions | `make test` |
| Every endpoint has a happy-path test and at least one failure test | Review your test file |
| No blocking calls inside `async def` | `/health` stays responsive under load |
| Runs in Docker from a clean clone | `docker compose up` |
| CI green on GitHub | Actions tab |
| README explains *design decisions*, not just usage | A stranger can run it in 5 minutes |

---

## Suggested structure

```
document-service/
├── .github/workflows/ci.yml
├── .pre-commit-config.yaml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── uv.lock
├── README.md
├── src/document_service/
│   ├── __init__.py
│   ├── api.py                  app, lifespan, middleware, exception handlers
│   ├── config.py               Settings
│   ├── logging_config.py
│   ├── models.py               Pydantic request/response models
│   ├── domain.py               Document, Chunk — the core types
│   ├── chunking.py             the chunking logic, pure and testable
│   ├── storage/
│   │   ├── base.py             Protocol — the interface Chapter 12 will reimplement
│   │   ├── memory.py           in-memory, for tests
│   │   └── sqlite.py           real persistence
│   ├── dependencies.py         Depends providers
│   └── routes/
│       ├── health.py
│       ├── documents.py
│       └── chunks.py
└── tests/
    ├── conftest.py
    ├── test_chunking.py        pure logic — fast, exhaustive
    ├── test_storage.py         run the SAME suite against both implementations
    ├── test_api_documents.py
    ├── test_api_streaming.py
    └── test_config.py
```

> **The detail worth copying:** `test_storage.py` runs one parametrized suite against both
> the memory and SQLite implementations. That's how you prove they're interchangeable — and
> it's what will let you drop in a vector store in Chapter 12 with confidence.

---

## Docker

```dockerfile
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ src/
RUN uv sync --frozen --no-dev


FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://localhost:8000/health').status_code==200 else 1)"

CMD ["uvicorn", "document_service.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Three things here are deliberate and worth understanding rather than copying blindly:

- **Multi-stage build** — build tools stay out of the final image. Smaller, less attack
  surface.
- **Dependencies before source** — Docker caches layers. Editing your code doesn't
  reinstall dependencies, which turns a 90-second rebuild into a 3-second one.
- **Non-root user** — a container running as root is a container one bug away from a bad
  day.

---

## Acceptance criteria

Work through this list literally. Every line is something a reviewer would check.

**Correctness**
- [ ] All nine endpoints work as specified
- [ ] Chunk character offsets are exact — slicing the original text by them reproduces the chunk
- [ ] Re-ingesting identical content returns the existing document, not a duplicate
- [ ] Pagination works and is correct at the boundaries (empty, one page, exact multiple)
- [ ] `DELETE` removes chunks too — no orphans left behind

**Robustness**
- [ ] Oversized upload → 413 with a useful message
- [ ] Wrong content type → 415
- [ ] `overlap >= size` → 422, with the field named
- [ ] Missing document → 404, not a 500
- [ ] Malformed JSON → 422, not a stack trace
- [ ] Empty document → handled deliberately (decide the behaviour, then test it)

**Async correctness**
- [ ] `/health` responds instantly while a large document reprocesses
- [ ] Client disconnect mid-stream stops the work and logs it
- [ ] No `time.sleep`, `requests`, or blocking file I/O in any `async def`
- [ ] All storage calls are genuinely async

**Quality**
- [ ] `make check` green
- [ ] Coverage ≥ 85%
- [ ] Every `# type: ignore` has a comment explaining why
- [ ] No secrets in the repo — verify with `git log -p | grep -i "key\|secret\|token"`

**Delivery**
- [ ] `docker compose up` works from a clean clone
- [ ] CI green
- [ ] README a stranger can follow in five minutes

---

## Stretch goals

Only after everything above is green. Each teaches something you'll use later:

1. **Markdown-aware chunking** — split on headings rather than word counts, preserving
   section titles as metadata. This is a direct preview of Chapter 11, and it's the single
   highest-value stretch here.
2. **PDF support** via `pypdf`. Discover how messy real PDFs are. Valuable disillusionment.
3. **Rate limiting** with `slowapi` — per-IP limits, 429 responses.
4. **Prometheus metrics** at `/metrics` — request counts, latency histograms.
5. **Postgres** instead of SQLite, via `asyncpg` — proves the storage interface was real.
6. **A Flutter client.** A small app that uploads a document and shows chunking progress
   from the SSE stream. This is your edge showing up in week 4, and it makes the project
   memorable in a way a backend alone never is.

---

## How to present it

The project is half the work. Being able to *talk* about it is the other half, and it's the
half candidates neglect.

Your README must answer these, in this order:

1. **What it does** — two sentences, no jargon.
2. **Quickstart** — clone to running in under five minutes. Test this on a friend.
3. **Design decisions** — the section that matters most. For each significant choice: what
   you chose, what you rejected, and *why*.
4. **Testing strategy** — what you test, what you deliberately don't, and why.
5. **What I'd do differently** — self-awareness reads as seniority. Everyone has a list; only
   experienced engineers write it down.

Two questions you will be asked in an interview. Have real answers ready:

> **"Why did you put storage behind an interface?"**
> The weak answer is "good practice." The strong answer names the future: a vector database
> replaces it, and the interface is what makes that a swap rather than a rewrite.

> **"How do you know your chunking is correct?"**
> Point at the offset-fidelity test — the one that slices the original text by the recorded
> offsets and asserts it reproduces the chunk exactly. That's a property, not an example,
> and a reviewer will notice the difference.

---

## Before you start

**Do not open the Chapter 3 template and start editing.** Start from `uv init`, build it
yourself, and use the template only when you're stuck or at the end, to compare. The
struggle is the entire point — you'll remember what you built and forget what you copied.

**Timebox it.** Twenty-two hours. If you're at hour thirty and polishing, stop: ship it,
write the README, move to Chapter 5. Part II waits for nobody, and a finished B+ project
beats an unfinished A+ one every single time.

---

<div align="center">

**[← Chapter 4](../ch04-async-and-fastapi/)** · **[The Book](../../readme.md)** · **[Chapter 5 → What an LLM Actually Is](../../part-2-language-models/ch05-what-an-llm-is/)**

*End of Part I · Week 4 of 34*

</div>
