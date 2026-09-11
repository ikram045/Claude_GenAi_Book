# Chapter 4 · Async & FastAPI

### Serving models over HTTP, and the streaming that makes AI products feel alive

> **Week 3 · ~22 hours · Heavy code**
>
> The last chapter before you touch a model. Everything you build from Chapter 6 onward
> will be served by something that looks very much like what you build here.

---

## 4.0 · Why this chapter exists

Every AI product you will ever build has the same shape:

```
    client  ──HTTP──▶  your server  ──HTTP──▶  the model provider
       ◀──streaming──      │
                           └──▶ your database, your vector store, your tools
```

Your server sits in the middle. It spends nearly all of its life **waiting** — for the
model, for the vector store, for a tool call to come back. A single request to a language
model can take five to thirty seconds, which is an eternity in web terms.

That single fact determines everything about how these servers are built:

- If your server handles requests one at a time, it can serve perhaps two users. Async is
  not an optimisation here; it is the difference between a product and a toy.
- If the user stares at a spinner for twenty seconds, they leave. **Streaming** is not a
  nicety — it is the single biggest perceived-quality lever in AI products, and it is
  mostly a server-side concern.
- If one slow request can block every other request, you will discover this in production
  at the worst possible moment.

You already understand async — you've built Flutter apps that fetch, stream and rebuild.
What's new is applying it on the server side, where the mistakes are less visible and more
expensive.

By the end of this chapter you'll have a typed, tested, streaming HTTP API. In Chapter 6 you
will swap the fake token generator for a real model, and almost nothing else will change.

---

## 4.1 · Concurrency is not parallelism

Worth thirty seconds of precision, because conflating these is the root of most async
confusion.

**Parallelism** is doing many things *at the same instant*. It requires multiple CPU cores
actually executing simultaneously.

**Concurrency** is *making progress* on many things in overlapping periods. One worker,
switching between tasks whenever one is stuck waiting.

The classic image: one cook with four pots. They aren't stirring four pots simultaneously —
they stir one, and while it simmers, they chop for the next. One worker, four dishes
progressing. That's concurrency, and it's exactly what `asyncio` gives you.

Now the crucial question: **what is your program actually waiting for?**

| Work type | Bottleneck | Right tool |
|---|---|---|
| **I/O-bound** — network calls, disk, database | Waiting on something else | `asyncio` ✅ |
| **CPU-bound** — number crunching, parsing, embedding maths | Your own processor | Processes, or a C library |

LLM application work is **overwhelmingly I/O-bound**. You call an API and wait. You query a
vector store and wait. You call a tool and wait. Almost none of your server's time is spent
computing — it's spent waiting on someone else's computer.

This is why `asyncio` is a near-perfect fit, and why Python's Global Interpreter Lock —
which cripples CPU parallelism — barely matters to you. While one request waits on the
model, the event loop runs a hundred others. A single Python process can comfortably hold
thousands of in-flight LLM requests, because each one is doing nothing but waiting.

> **Coming from Flutter:** this is exactly the model you already live in. Dart is
> single-threaded with an event loop; `await` yields control; heavy computation goes to an
> Isolate. Python's event loop is the same shape, and `multiprocessing` is the Isolate.
> You're not learning a new paradigm — you're learning new spelling for one you use daily.

---

## 4.2 · The event loop

A quick look under the hood, because you'll debug this eventually.

The event loop is a queue and a `while` loop. It picks a ready task, runs it until the task
hits an `await` on something unfinished, parks it, and picks the next ready task. When a
parked task's data arrives, it goes back in the queue.

```
  ┌─────────────────────────────────────────┐
  │              EVENT LOOP                 │
  │                                         │
  │   ready queue:  [ T1 ] [ T4 ] [ T7 ]    │
  │        │                                │
  │        ▼   run until it awaits          │
  │     ┌─────┐                             │
  │     │ T1  │──await http──▶ parked       │
  │     └─────┘                             │
  │        │                                │
  │        ▼   next ready task              │
  │     ┌─────┐                             │
  │     │ T4  │                             │
  │     └─────┘                             │
  │                                         │
  │   parked:  T2 (db)  T3 (model)  T5 (io) │
  │            ↑ return to queue when ready │
  └─────────────────────────────────────────┘
```

The entire arrangement rests on one assumption: **every task yields control promptly.**

Break that assumption and everything stops. If one task runs a tight loop for two seconds
without awaiting, the loop cannot run anything else for two seconds. Every other request
hangs. This is *the* async failure mode, and section 4.14 is devoted to it.

```python
# ❌ Freezes the entire server for 2 seconds. Every user. Every request.
async def handler():
    time.sleep(2)
    return "done"

# ✅ Yields control. Other requests proceed.
async def handler():
    await asyncio.sleep(2)
    return "done"
```

---

## 4.3 · The async patterns that matter

Chapter 2 covered the syntax. These are the five patterns you'll use in real server code.

### Pattern 1 · Concurrent fan-out

Ten independent calls should take as long as the slowest, not the sum.

```python
# ❌ Sequential — 10 × 200ms = 2000ms
results = []
for url in urls:
    results.append(await fetch(url))

# ✅ Concurrent — ≈ 200ms
results = await asyncio.gather(*(fetch(u) for u in urls))
```

You'll do this constantly: embedding many chunks, querying several retrievers, calling
several tools a model requested in one turn.

### Pattern 2 · TaskGroup — the modern, safer `gather`

Python 3.11 introduced `TaskGroup`, and it's what you should reach for by default:

```python
async def fetch_all(urls: list[str]) -> list[str]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(u)) for u in urls]
    return [t.result() for t in tasks]
```

The difference from `gather` is **structured concurrency**: if any task fails, the others
are *cancelled* and the group raises. No task can outlive its block. With bare `gather`, a
failure leaves siblings running in the background, quietly consuming rate limit and money
for a request that already failed.

Failures arrive as an `ExceptionGroup`, which you catch with `except*`:

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch(a))
        tg.create_task(fetch(b))
except* ConnectionError as eg:
    logger.warning("%d connection failures", len(eg.exceptions))
except* ValueError as eg:
    logger.error("%d bad values", len(eg.exceptions))
```

Use `gather(..., return_exceptions=True)` when you genuinely want partial success — "embed
these 500 chunks, tell me which failed, keep the rest." Use `TaskGroup` when a failure
means the whole operation is void.

### Pattern 3 · Bounded concurrency

Unbounded concurrency is a real bug, not a theoretical one. Fire 10,000 requests at a
provider and you'll get rate-limited, blocked, or billed for a mistake.

```python
sem = asyncio.Semaphore(10)          # at most 10 in flight

async def fetch_limited(url: str) -> str:
    async with sem:
        return await fetch(url)

results = await asyncio.gather(*(fetch_limited(u) for u in urls))
```

All 10,000 coroutines are created immediately — they're cheap — but only ten are ever
actually running. Memorise this pattern. You will use it in every chapter of Part III.

### Pattern 4 · Timeouts

Never make a network call without one. A hung connection with no timeout hangs forever,
and "forever" in a server means a leaked task and eventually an exhausted pool.

```python
async with asyncio.timeout(30):          # 3.11+
    result = await slow_operation()
# raises TimeoutError if it overruns
```

### Pattern 5 · Fire-and-forget, done correctly

```python
# ❌ The task may be garbage-collected mid-flight. Real bug, hard to reproduce.
asyncio.create_task(log_analytics(event))

# ✅ Keep a reference until it completes
_background: set[asyncio.Task] = set()

def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)
```

The event loop holds only a *weak* reference to tasks. Without a strong reference of your
own, a task can vanish partway through. FastAPI's `BackgroundTasks` (section 4.12) handles
this for you, which is why you should prefer it inside request handlers.

### Cancellation

When a task is cancelled, `CancelledError` is raised *inside it* at its current `await`.
Clean up in `finally`, and always re-raise:

```python
async def worker() -> None:
    try:
        await long_operation()
    except asyncio.CancelledError:
        logger.info("cancelled, cleaning up")
        raise                       # ← never swallow this
    finally:
        await release_resources()
```

Swallowing `CancelledError` produces tasks that refuse to die and shutdowns that hang. It
is the async equivalent of catching every exception and ignoring it.

---

## 4.4 · `httpx` — the async HTTP client

`requests` is the famous Python HTTP library and it is **synchronous** — using it in an
async server blocks the event loop. Use `httpx`: same ergonomics, async-native.

```python
import httpx

# ❌ New connection per request. Slow, and exhausts sockets under load.
async def bad(url: str) -> str:
    async with httpx.AsyncClient() as client:
        return (await client.get(url)).text

# ✅ One shared client, reused. Connection pooling, keep-alive.
client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=5.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
)

async def good(url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.text
```

> **Create one client for your application's lifetime.** Creating a client per request
> throws away connection pooling and TLS session reuse, which on a hot path costs real
> latency. Section 4.12 shows where to put it.

Streaming a response body — the mechanism underneath every streaming LLM call:

```python
async def stream_download(url: str) -> AsyncIterator[bytes]:
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            yield chunk
```

---

## 4.5 · Why FastAPI

FastAPI is two things stitched together with unusual taste: **Starlette** (an async web
framework) and **Pydantic** (the validation library from Chapter 2).

That combination produces something you'll appreciate coming from a typed language: **your
type annotations become the API contract.** Declare a Pydantic model as a parameter and
FastAPI parses the body, validates it, coerces types, returns a precise 422 on bad input,
and generates OpenAPI documentation — all from the annotation. No decorators describing the
schema, no separate spec file that drifts out of date.

It's also the default in this field. Nearly every AI service you'll encounter is FastAPI.

```bash
uv add fastapi uvicorn[standard]
uv add --dev pytest-asyncio httpx
```

`uvicorn` is the ASGI server that actually runs your app.

---

## 4.6 · Your first endpoint

```python
# src/genai_toolkit/api.py
from fastapi import FastAPI

app = FastAPI(title="GenAI Toolkit", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

```bash
uv run uvicorn genai_toolkit.api:app --reload
```

Three URLs to open immediately:

- `http://127.0.0.1:8000/health` — your endpoint
- `http://127.0.0.1:8000/docs` — **interactive documentation, generated from your types**
- `http://127.0.0.1:8000/openapi.json` — the machine-readable spec

That `/docs` page is generated entirely from annotations. It's the payoff for the typing
discipline from Chapter 3, and it's genuinely useful — you can call your API from the
browser while developing.

### `async def` vs `def` — a nuance that matters

FastAPI accepts both, and treats them **differently**:

```python
@app.get("/a")
async def a():      # runs ON the event loop
    ...

@app.get("/b")
def b():            # runs in a THREAD POOL, automatically
    ...
```

If your handler is `def` (not `async def`), FastAPI runs it in a thread pool so blocking
code can't freeze the loop. That's a thoughtful safety net.

**The dangerous case is the mix:** an `async def` handler that calls blocking code. FastAPI
trusts your `async` declaration and runs it on the loop, where your blocking call stops
everything.

> **The rule:** `async def` + `await` everything, or plain `def` if you must call blocking
> libraries. Never `async def` with blocking code inside. This is the most common
> performance bug in FastAPI applications.

---

## 4.7 · Request and response models

This is where FastAPI earns its reputation.

```python
from pydantic import BaseModel, Field


class ChunkRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    size: int = Field(default=50, ge=1, le=1000)
    overlap: int = Field(default=10, ge=0)
    source: str = "inline"


class ChunkResponse(BaseModel):
    chunks: list[str]
    count: int
    total_words: int


@app.post("/chunk", response_model=ChunkResponse)
async def chunk(request: ChunkRequest) -> ChunkResponse:
    if request.overlap >= request.size:
        raise HTTPException(422, "overlap must be smaller than size")

    chunks = list(chunk_text(request.text, request.source, request.size, request.overlap))
    return ChunkResponse(
        chunks=[c.text for c in chunks],
        count=len(chunks),
        total_words=sum(c.word_count for c in chunks),
    )
```

Everything below happens because of that one annotation `request: ChunkRequest`:

- The JSON body is parsed.
- Every field is validated and coerced. `"50"` becomes `50`; `size: 5000` is rejected.
- Invalid input returns **422** with a precise field-level error — no code from you.
- `/docs` shows the exact schema, with an editable example.
- Your editor and mypy know the types throughout.

Bad input produces this, automatically:

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "size"],
      "msg": "Input should be greater than or equal to 1",
      "input": 0
    }
  ]
}
```

`response_model` does the same on the way out: it validates and **filters** the response, so
a field not declared in `ChunkResponse` is stripped rather than leaked. That filtering is a
genuine security feature — it's how you avoid accidentally returning a password hash
because someone added a column.

### Where parameters come from

FastAPI infers the source from the type, and you can be explicit:

```python
from fastapi import Body, Header, Path, Query


@app.get("/search/{index}")
async def search(
    index: str = Path(description="Index to search"),          # URL path
    q: str = Query(min_length=1, max_length=500),              # ?q=...
    limit: int = Query(default=10, ge=1, le=100),              # ?limit=...
    api_key: str | None = Header(default=None),                # X-API-Key header
) -> list[str]:
    ...
```

Rules of thumb: Pydantic models come from the body, scalars from the query string, anything
named in the path template from the path.

---

## 4.8 · Dependency injection

FastAPI's `Depends` is its second great idea, and you already know why it matters — it's
the same problem Riverpod and Provider solve in Flutter.

```python
from typing import Annotated
from fastapi import Depends


async def get_client() -> httpx.AsyncClient:
    return app.state.http_client


async def get_current_user(
    api_key: Annotated[str | None, Header()] = None,
) -> User:
    if api_key is None:
        raise HTTPException(401, "missing API key")
    user = await lookup_user(api_key)
    if user is None:
        raise HTTPException(401, "invalid API key")
    return user


# Name the dependency once, reuse it everywhere
CurrentUser = Annotated[User, Depends(get_current_user)]
HttpClient = Annotated[httpx.AsyncClient, Depends(get_client)]


@app.get("/me")
async def me(user: CurrentUser) -> User:
    return user


@app.post("/search")
async def search(q: str, user: CurrentUser, client: HttpClient) -> list[str]:
    ...
```

What you get:

- **Reuse** — authentication written once, applied by annotation.
- **Testability** — `app.dependency_overrides[get_current_user] = fake_user` swaps it out in
  tests. No mocking library, no patching.
- **Composition** — dependencies can depend on dependencies, resolved automatically.
- **Documentation** — the auth requirement shows up in `/docs`.

Dependencies with cleanup use `yield`, exactly like pytest fixtures:

```python
async def get_db() -> AsyncIterator[Connection]:
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()      # runs after the response is sent
```

That `Annotated[...]` alias pattern — `CurrentUser`, `HttpClient` — is the idiom worth
adopting. It keeps signatures readable as the dependency list grows.

---

## 4.9 · Errors

```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="index not found")
```

For your own exception types, register a handler once and raise domain errors freely:

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class RetrievalError(Exception):
    def __init__(self, message: str, index: str) -> None:
        super().__init__(message)
        self.message, self.index = message, index


@app.exception_handler(RetrievalError)
async def handle_retrieval_error(request: Request, exc: RetrievalError) -> JSONResponse:
    logger.error("retrieval failed on %s: %s", exc.index, exc.message)
    return JSONResponse(
        status_code=503,
        content={"error": "retrieval_unavailable", "detail": exc.message},
    )
```

Now your business logic raises `RetrievalError` and never imports anything web-related —
the separation you'd want anyway.

> **Never leak internals in error responses.** A stack trace or raw provider error can
> expose file paths, library versions, prompt contents, or fragments of another user's
> data. Log the detail, return something generic. You'll revisit this properly in
> Chapter 24.

---

## 4.10 · Streaming — the important part

This is the section that matters most for everything you build after Chapter 6.

### Why it matters

A model takes fifteen seconds to write a long answer. Two possible experiences:

| | Non-streaming | Streaming |
|---|---|---|
| First visible text | 15s | ~0.4s |
| Feels like | Broken | Thinking |
| User behaviour | Leaves | Reads along |

Total time is identical. **Perceived** speed differs by an order of magnitude. Time to
first token is the metric users actually feel, and it's almost entirely within your control.

### Server-Sent Events

SSE is the right transport for this: one-directional server-to-client, plain HTTP, auto-
reconnecting, no WebSocket complexity. It's what essentially every chat product uses.

The wire format is deliberately trivial — `data: ` then your payload, then **two** newlines:

```
data: {"text": "Hello"}

data: {"text": " world"}

data: [DONE]

```

That blank line between events is the message delimiter. Forget it and the client buffers
forever, which is the single most common SSE bug.

### Implementation

```python
import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse


async def fake_token_stream(prompt: str) -> AsyncIterator[str]:
    """Stand-in for a model. Chapter 6 replaces the body; the shape stays identical."""
    for word in f"You said: {prompt}. Here is a thoughtful reply.".split():
        await asyncio.sleep(0.05)
        yield word + " "


async def sse_events(prompt: str) -> AsyncIterator[str]:
    try:
        async for token in fake_token_stream(prompt):
            yield f"data: {json.dumps({'text': token})}\n\n"
    except Exception as exc:
        logger.exception("stream failed")
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        sse_events(request.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",     # tells nginx not to buffer
        },
    )
```

Test it from a terminal:

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello"}'
```

The `-N` disables curl's own buffering. Without it you'll see everything arrive at once and
conclude streaming is broken when it isn't.

### The four things that break streaming

Every one of these has cost somebody a day:

1. **A missing blank line.** `\n\n` terminates an event. One `\n` and the client waits
   forever.
2. **A buffering proxy.** nginx buffers responses by default. `X-Accel-Buffering: no` and
   `proxy_buffering off;` fix it. Your code is fine; the infrastructure is eating it.
3. **Errors mid-stream.** Status 200 was already sent — you cannot now return a 500. You
   must send the error *as an event* and let the client handle it. This is why the
   `try/except` above lives inside the generator.
4. **Client disconnects.** The user closed the tab; you're still paying the provider for
   tokens nobody will read. Check and bail:

```python
from fastapi import Request

async def sse_events(request: Request, prompt: str) -> AsyncIterator[str]:
    async for token in fake_token_stream(prompt):
        if await request.is_disconnected():
            logger.info("client gone, abandoning generation")
            break
        yield f"data: {json.dumps({'text': token})}\n\n"
```

> **Note the shape of `sse_events`.** It's an async generator — the exact construct from
> section 2.14. Everything you learned about generators applies: lazy, single-use, cleanup
> in `finally`. If you built Flutter UIs on a `StreamBuilder`, you've written the client
> half of this many times.

---

## 4.11 · Lifespan and background tasks

### Lifespan — startup and shutdown

This is where the shared resources go: the HTTP client, the database pool, the embedding
model.

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    app.state.http_client = httpx.AsyncClient(timeout=settings.request_timeout)
    logger.info("startup complete")

    yield                                   # ← the application runs here

    await app.state.http_client.aclose()
    logger.info("shutdown complete")


app = FastAPI(title="GenAI Toolkit", lifespan=lifespan)
```

Same `@asynccontextmanager` shape as the timer in section 2.15. Setup before `yield`,
teardown after, guaranteed.

### Background tasks

Work that should happen *after* the response is sent — logging, analytics, cache warming:

```python
from fastapi import BackgroundTasks


@app.post("/chat")
async def chat(request: ChatRequest, background: BackgroundTasks) -> ChatResponse:
    answer = await generate(request.prompt)
    background.add_task(record_usage, request.prompt, answer)   # after the response
    return ChatResponse(answer=answer)
```

FastAPI holds the reference for you, which sidesteps the garbage-collection trap from
section 4.3.

> **Know the limit.** `BackgroundTasks` runs in the same process. If it crashes, the work is
> silently lost; if the process restarts, in-flight tasks vanish. It's right for
> fire-and-forget logging, wrong for anything that must not be lost. That needs a real queue
> — Chapter 26.

---

## 4.12 · Middleware and CORS

Middleware wraps every request. The canonical use is timing and request IDs:

```python
import time
import uuid


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    response = await call_next(request)

    elapsed = time.perf_counter() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.3f}"
    logger.info("%s %s %s %d %.3fs", request_id, request.method,
                request.url.path, response.status_code, elapsed)
    return response
```

That request ID becomes essential in Chapter 23, when you need to correlate a user's
complaint with a specific trace.

CORS, if a browser will call your API:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],     # never ["*"] with credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> **Middleware runs on every request, including streaming ones.** Don't do anything slow in
> it, and be careful with anything that tries to read or modify the response body — it will
> break streaming by buffering it.

---

## 4.13 · Testing

FastAPI is unusually pleasant to test, because dependency injection removes the need for
mocking frameworks.

```python
# tests/test_api.py
import pytest
from httpx import ASGITransport, AsyncClient

from genai_toolkit.api import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_chunk_validates_input(client: AsyncClient) -> None:
    response = await client.post("/chunk", json={"text": "", "size": 10})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "text"]


async def test_chunk_rejects_bad_overlap(client: AsyncClient) -> None:
    response = await client.post("/chunk", json={"text": "a b c", "size": 2, "overlap": 5})
    assert response.status_code == 422
```

The requests never touch the network — `ASGITransport` calls your app in-process, so tests
are fast and deterministic.

### Overriding dependencies

```python
async def fake_user() -> User:
    return User(id="test-user", name="Test")


@pytest.fixture
def authed_app():
    app.dependency_overrides[get_current_user] = fake_user
    yield app
    app.dependency_overrides.clear()      # always clean up
```

No `unittest.mock`, no patching. You swap the dependency.

### Testing a stream

```python
async def test_stream_ends_with_done(client: AsyncClient) -> None:
    events: list[str] = []
    async with client.stream("POST", "/chat/stream", json={"prompt": "hi"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(line.removeprefix("data: "))

    assert len(events) > 1, "should stream multiple events, not one blob"
    assert events[-1] == "[DONE]"
```

That `len(events) > 1` assertion is the important one. It's the test that catches a
"streaming" endpoint that actually buffers everything and sends it in one chunk — a bug
that's invisible to the eye and obvious to this test.

---

## 4.14 · What breaks in production

Four failure modes, in rough order of how often they bite people.

### 1 · Blocking the event loop

The big one. Any synchronous call inside `async def` freezes every concurrent request.

```python
# ❌ Every one of these stops the world
async def handler():
    time.sleep(1)                       # → await asyncio.sleep(1)
    requests.get(url)                   # → await httpx client
    open("big.txt").read()              # → aiofiles, or to_thread
    pandas.read_csv("huge.csv")         # → asyncio.to_thread
    embeddings = model.encode(texts)    # CPU-bound → to_thread or a worker
```

The fix when you must call blocking code:

```python
result = await asyncio.to_thread(blocking_function, arg)
```

**How to detect it:** hit one slow endpoint while polling `/health` in another terminal. If
`/health` stalls, you're blocking the loop. Also run with
`PYTHONASYNCIODEBUG=1`, which logs any callback taking over 100ms.

### 2 · Unbounded concurrency

No `Semaphore` means a traffic spike becomes 5,000 simultaneous provider calls, a rate-limit
wall, and a large bill. Bound everything that leaves your process.

### 3 · No timeouts

A hung upstream connection holds a task and a socket forever. Under sustained load, you leak
until the process dies. Every network call gets a timeout.

### 4 · Resource leaks

Creating an `httpx.AsyncClient` per request exhausts file descriptors under load. One client
in lifespan, injected via `Depends`.

### Running it for real

```bash
# Development
uv run uvicorn genai_toolkit.api:app --reload

# Production — multiple worker processes to use multiple cores
uv run uvicorn genai_toolkit.api:app --host 0.0.0.0 --port 8000 --workers 4
```

Workers are separate **processes**, which is how you get past the GIL. Consequence worth
internalising: **they share no memory**. Anything in a module-level dict exists separately
in each worker, so in-process caches give inconsistent results across requests. Shared state
belongs in Redis or a database. Chapter 26 covers this properly.

---

## 4.15 · Build it

Extend the Chapter 3 template into a real service. Add to `src/genai_toolkit/`:

```
api.py            FastAPI app, lifespan, middleware, exception handlers
routes/
  health.py       GET  /health   — liveness
  chunk.py        POST /chunk    — Chapter 2's chunker, over HTTP
  chat.py         POST /chat          (non-streaming, fake model)
                  POST /chat/stream   (SSE, fake model)
dependencies.py   get_settings, get_http_client, get_current_user
```

Requirements — treat these as the spec:

1. `/health` returns `{"status": "ok"}` and stays responsive **while `/chat/stream` is
   running**. This is the test that proves you didn't block the loop.
2. `/chunk` validates with Pydantic and returns 422 with field-level detail on bad input.
3. `/chat/stream` emits proper SSE, terminates with `[DONE]`, and stops generating when the
   client disconnects.
4. One `httpx.AsyncClient`, created in lifespan, injected with `Depends`.
5. Middleware logs method, path, status and duration with a request ID.
6. A custom exception type with a registered handler.
7. Tests cover: health, validation failure, a successful chunk, the stream producing
   multiple events, and a dependency override.
8. `make check` passes — ruff clean, mypy strict clean, tests green.

**Then break it deliberately**, and watch what happens each time:

- Put `time.sleep(5)` in an `async def` handler. Poll `/health` while it runs. Feel the
  freeze — this is the lesson of the chapter.
- Change it to `await asyncio.sleep(5)`. Poll again. Notice `/health` stays instant.
- Remove one `\n` from the SSE format. Watch `curl -N` hang with nothing to show.
- Remove the semaphore from a fan-out endpoint and fire 500 concurrent requests at a slow
  fake upstream. Watch the queue collapse.

---

## 4.16 · Exercises

**1 · Time the three strategies.** Write an endpoint that calls a slow fake upstream 20
times: sequentially, with `gather`, and with `gather` + `Semaphore(5)`. Return the elapsed
time for each. Explain the numbers you get.

**2 · Prove the loop blocks.** Two endpoints, `/blocking` (`time.sleep(3)`) and
`/non-blocking` (`await asyncio.sleep(3)`). Hit each while polling `/health`. Write down
what you observed — you'll want this memory later.

**3 · Stream with metadata.** Extend `/chat/stream` to emit a first event with
`{"type": "start", "request_id": ...}`, then `{"type": "token", ...}` events, then
`{"type": "done", "token_count": n, "elapsed_ms": n}`. This is the shape of every real
streaming AI API.

**4 · Handle disconnects.** Add `request.is_disconnected()` checking. Prove it works: start
a curl, kill it mid-stream, and confirm your log shows the generation was abandoned.

**5 · Error mid-stream.** Make the generator raise on the fifth token. Ensure the client
receives a well-formed error event rather than a truncated stream. Test it.

**6 · A dependency with cleanup.** Write a `Depends` that opens a resource, yields it, and
closes it — with logging proving the close happens even when the handler raises.

**7 · Convert the chunker.** Turn Chapter 2's chunker into a `POST /chunk` endpoint with
full validation, then write five tests covering the validation boundaries.

**8 · A retry dependency.** Wire the `retry` function from Chapter 2's exercises into an
endpoint that calls a flaky upstream. Log each attempt. Confirm the endpoint succeeds even
when the upstream fails twice.

---

## 4.17 · Checkpoint

> **Move on to Part II when all of these are true.**

**Explain, out loud, without looking:**

1. Why async matters more for LLM servers than for typical CRUD APIs.
2. The difference between concurrency and parallelism, and which one `asyncio` provides.
3. What happens when you call `time.sleep()` inside an `async def` FastAPI handler.
4. Why `TaskGroup` is usually safer than bare `gather`.
5. How SSE works on the wire, and what the blank line is for.
6. Why `async def` and `def` handlers are treated differently by FastAPI.

**Write, from memory:**

7. A FastAPI endpoint with a Pydantic request model and `response_model`.
8. A streaming SSE endpoint with a proper `[DONE]` terminator and error handling.
9. A `Depends` dependency with `yield`-based cleanup.
10. A test that asserts a stream produces **more than one** event.

**Verify:**

11. `/health` stays responsive while a 10-second stream is running.
12. `curl -N` shows tokens arriving progressively, not all at once.
13. Killing the client mid-stream logs an abandoned generation.
14. `make check` is green.

Number 11 is the one that matters. If `/health` stalls, something in your handler is
blocking the event loop, and finding it is the most valuable debugging you'll do this week.

---

## 4.18 · Going deeper (optional)

**The FastAPI documentation** is genuinely excellent — one of the best in any ecosystem.
The "Advanced User Guide" sections on dependencies and custom responses are worth an hour.

**If you want to understand ASGI:** read the ASGI specification. It's short, and it
demystifies what `uvicorn`, Starlette and FastAPI each actually do. Knowing that an ASGI app
is just `async def app(scope, receive, send)` makes the whole stack stop feeling magical.

**If async still feels shaky:** search for "structured concurrency" and read about
`TaskGroup`'s design. The argument for why unstructured `create_task` is harmful will change
how you write concurrent code, in any language.

**If you want to see the future of this chapter:** look at the SSE format used by the
Anthropic Messages API streaming endpoint. You'll recognise every part of it now, and in
Chapter 6 you'll consume it for real.

---

<div align="center">

**[← Chapter 3](../ch03-modern-toolchain/)** · **[The Book](../../readme.md)** · **[Project A → Typed API](../project-a-typed-api/)**

*Chapter 4 of 31 · Week 3 · End of Part I theory*

</div>
