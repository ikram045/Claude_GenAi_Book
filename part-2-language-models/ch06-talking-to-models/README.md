# Chapter 6 · Talking to Models

### The API, properly — requests, streaming, errors, and the shape of every AI app you'll build

> **Week 6 · ~22 hours · Heavy code**
>
> Your first API key. By the end of this week you'll have a streaming CLI assistant you
> actually use, and every pattern in it will reappear in Parts III, IV and V.

---

## 6.0 · Why this chapter exists

There are two ways to learn an LLM API.

The first is to copy the four-line example from the documentation, get a response, and feel
finished. This takes ten minutes and leaves you unable to build anything real, because the
four-line example omits streaming, errors, retries, cost tracking, concurrency, caching, and
conversation state — which is to say, it omits the entire application.

The second is to learn the request/response cycle thoroughly enough that when something goes
wrong in production at 2am, you know where to look. That takes a week, and it's what this
chapter is.

The good news is that the surface is genuinely small. One endpoint, a handful of parameters,
one response shape. The depth is in the operational details: what to do when you're rate
limited, how to stream without blocking, how to know what a request cost you, how to keep a
conversation from growing until it breaks.

> **A note on version drift.** Model names, prices and parameters in this chapter are a
> snapshot. This field moves. The *shapes* — a stateless messages array, content blocks, a
> stop reason, usage accounting, streaming events — have been stable for years and will
> outlive every specific identifier printed here. Learn the shapes; look up the specifics.

---

## 6.1 · Setup

```bash
uv add anthropic
```

### Getting a key

Create one in the Anthropic Console. Then, following Chapter 3's discipline:

```bash
# .env  — never committed
ANTHROPIC_API_KEY=sk-ant-...
```

```bash
# .env.example  — committed
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

> **Before you write any code:** confirm `git check-ignore -v .env` prints a rule. Keys have
> been scraped from public repositories within minutes of being pushed. If you ever do leak
> one, **rotate it immediately** — deleting the commit does not help, because history is
> forever and scrapers are fast.

### The client

```python
import anthropic

client = anthropic.Anthropic()          # reads credentials from the environment
async_client = anthropic.AsyncAnthropic()
```

The zero-argument constructor resolves credentials in order: the `ANTHROPIC_API_KEY`
environment variable, then `ANTHROPIC_AUTH_TOKEN`, then a profile stored by the CLI's
`ant auth login`. So an unset `ANTHROPIC_API_KEY` does **not** necessarily mean you have no
credentials — check `ant auth status` before concluding anything.

Prefer the zero-argument form. Hardcoding a key, even temporarily, is how keys end up in git.

### Your first request

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    messages=[{"role": "user", "content": "Explain embeddings in two sentences."}],
)

for block in response.content:
    if block.type == "text":
        print(block.text)
```

Run it. That's a real language model responding to you, and you just paid a fraction of a
cent for it.

Now let's take that apart properly, because every line of it is a decision.

---

## 6.2 · Anatomy of a request

### `model`

Which model to use. A snapshot of the current lineup:

| Model | ID | Context | Input $/1M | Output $/1M |
|---|---|:---:|---:|---:|
| Claude Opus 5 | `claude-opus-5` | 1M | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $2.00 | $10.00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

**Default to the most capable model while you're learning.** This is not extravagance — it's
methodology. If you start on a cheap model and results are poor, you cannot tell whether your
prompt is wrong or the model is underpowered, and you'll spend hours debugging the wrong
thing. Start where quality is highest, get it working, *then* measure whether something
cheaper holds up (Chapter 9). Cost optimisation is a decision made with evidence, not a
default you inherit.

Use the exact ID strings. Don't append date suffixes you half-remember — they'll 404.

### `max_tokens`

The ceiling on the **response**, in tokens. Required.

```python
max_tokens=16_000     # sensible default for non-streaming
max_tokens=64_000     # when streaming, give it room
max_tokens=256        # classification — you want a short answer anyway
```

> **Don't lowball this.** If generation hits the cap, the response is truncated
> mid-sentence, `stop_reason` comes back as `"max_tokens"`, and you pay for the truncated
> output *and* the retry. The cost of a high `max_tokens` is zero unless the model actually
> uses it — you're billed for tokens generated, not tokens permitted.
>
> The one constraint: very large values require streaming. The SDK will refuse a
> non-streaming request it estimates will exceed the HTTP timeout, because idle connections
> get dropped. That refusal is a feature.

### `messages`

The conversation, as a list. Alternating roles, starting with `user`.

```python
messages = [
    {"role": "user", "content": "My name is Ikram."},
    {"role": "assistant", "content": "Nice to meet you, Ikram."},
    {"role": "user", "content": "What's my name?"},
]
```

**The API is stateless.** The model has no memory between calls. That third question only
works because you resent the first two messages. This is section 5.10 made concrete, and it
has a cost consequence you'll feel by Chapter 9: every turn resends everything.

Content can also be a list of blocks, which is how you send images, documents, and cache
markers:

```python
{"role": "user", "content": [
    {"type": "text", "text": "What's in this image?"},
    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
]}
```

### `system`

Standing instructions that frame the entire conversation — role, rules, constraints, output
format. Not a message; a separate top-level parameter.

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    system="You are a concise technical assistant. Prefer examples over prose. "
           "If you are unsure, say so explicitly rather than guessing.",
    messages=[{"role": "user", "content": "How do I read a JSON file in Python?"}],
)
```

The system prompt carries more weight than the same words placed in a user message. It's
where persona, constraints and safety rules belong. Chapter 7 is entirely about writing these
well.

### `temperature`

From Chapter 5 — how much randomness in token selection.

```python
temperature=0       # extraction, classification, structured output
temperature=0.7     # conversation
```

**Check what your model accepts.** On models with adaptive thinking, `temperature` and
`top_p` are rejected outright — you steer with `effort` instead (section 6.6). Assuming
temperature always works is a common source of confusing 400s.

---

## 6.3 · Anatomy of a response

The response is not a string. Treat it as one and you'll break the moment you add thinking or
tools.

```python
response = client.messages.create(...)

response.id                  # "msg_01ABC..."
response.model               # which model actually served it
response.role                # "assistant"
response.content             # list of content BLOCKS  ← note this
response.stop_reason         # why it stopped
response.usage               # token accounting
response._request_id         # log this when reporting a problem to the provider
```

### Content blocks

`response.content` is a **list**, and each element has a `type`:

```python
for block in response.content:
    if block.type == "text":
        print(block.text)
    elif block.type == "thinking":
        print(f"[reasoning] {block.thinking}")
    elif block.type == "tool_use":
        print(f"[wants to call {block.name} with {block.input}]")
```

> **Always branch on `block.type`.** Writing `response.content[0].text` works right up until
> the first block is a thinking block or a tool use, at which point it raises an
> `AttributeError` in production. This is the single most common beginner bug against this
> API.

A small helper you'll use constantly:

```python
def text_of(response) -> str:
    """Concatenate every text block, ignoring thinking and tool blocks."""
    return "".join(b.text for b in response.content if b.type == "text")
```

### `stop_reason`

**Check this.** It tells you whether you got a complete answer.

| Value | Meaning | What to do |
|---|---|---|
| `end_turn` | Finished naturally | Normal path |
| `max_tokens` | Hit your cap — **truncated** | Raise `max_tokens`, or stream |
| `tool_use` | Wants to call a tool | Execute it, loop (Part IV) |
| `stop_sequence` | Hit a custom stop string | Usually intended |
| `pause_turn` | Paused, resumable | Continue the turn |
| `refusal` | Declined for safety reasons | Inspect `stop_details`; don't retry blindly |

```python
if response.stop_reason == "max_tokens":
    logger.warning("truncated response — raise max_tokens")
```

Silently ignoring `max_tokens` truncation produces the worst class of bug: a plausible,
well-formed, *incomplete* answer that no exception ever flagged.

### `usage` — what it cost

```python
u = response.usage
u.input_tokens                  # uncached input, full price
u.output_tokens                 # generated
u.cache_creation_input_tokens   # written to cache (~1.25× input price)
u.cache_read_input_tokens       # served from cache (~0.1× input price)
```

**Log these on every single request from day one.** Not because you need the data today, but
because in Chapter 9 you'll want to know where your money goes, and by then it's too late to
retroactively instrument.

```python
def cost_usd(usage, input_per_mtok: float, output_per_mtok: float) -> float:
    return (
        usage.input_tokens * input_per_mtok
        + usage.cache_read_input_tokens * input_per_mtok * 0.1
        + usage.cache_creation_input_tokens * input_per_mtok * 1.25
        + usage.output_tokens * output_per_mtok
    ) / 1_000_000
```

---

## 6.4 · Streaming

Chapter 4 built the server side. Now the client side, which is where the tokens come from.

### The simple form

```python
with client.messages.stream(
    model="claude-opus-5",
    max_tokens=64_000,
    messages=[{"role": "user", "content": "Explain retrieval-augmented generation."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

`flush=True` matters. Without it, Python buffers stdout and you'll see the whole response
appear at once, then conclude streaming is broken when it isn't. This is the client-side twin
of the `curl -N` lesson from Chapter 4.

### Getting the full message afterwards

The stream accumulates state, so you don't have to reassemble anything:

```python
with client.messages.stream(...) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

    final = stream.get_final_message()

print(f"\n\n{final.usage.output_tokens} output tokens, stop={final.stop_reason}")
```

> **Default to streaming, even when you don't display tokens.** `get_final_message()` gives
> you the complete response anyway, and streaming protects you from HTTP timeouts on long
> generations. There is very little reason not to.

### Async — the version you'll actually deploy

This is the shape that plugs directly into Chapter 4's `StreamingResponse`:

```python
from collections.abc import AsyncIterator

async def stream_answer(question: str) -> AsyncIterator[str]:
    async with async_client.messages.stream(
        model="claude-opus-5",
        max_tokens=64_000,
        messages=[{"role": "user", "content": question}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
```

That's an async generator — exactly the construct from section 2.14 and exactly what
Chapter 4's SSE endpoint consumes. The fake token generator you wrote in week 3 is now
replaced by a real model, and **nothing else in your server changes.** That's the payoff for
building the shape first.

### Event-level streaming

When you need more than text — reasoning blocks, tool calls, per-block boundaries — iterate
events instead:

```python
with client.messages.stream(...) as stream:
    for event in stream:
        if event.type == "content_block_start":
            if event.content_block.type == "thinking":
                print("\n[thinking…]")
        elif event.type == "content_block_delta":
            if event.delta.type == "thinking_delta":
                print(event.delta.thinking, end="", flush=True)
            elif event.delta.type == "text_delta":
                print(event.delta.text, end="", flush=True)
        elif event.type == "message_delta":
            if event.usage:
                tokens = event.usage.output_tokens
```

The event sequence: `message_start` → (`content_block_start` → many
`content_block_delta` → `content_block_stop`) per block → `message_delta` → `message_stop`.

---

## 6.5 · Errors and retries

Network calls fail. Provider calls fail more, because you're also subject to rate limits and
capacity.

```python
import anthropic

try:
    response = client.messages.create(...)

except anthropic.AuthenticationError:
    raise                                    # bad key — never retry, fix it

except anthropic.BadRequestError as e:
    logger.error("malformed request: %s", e.message)
    raise                                    # your bug — never retry

except anthropic.NotFoundError:
    logger.error("unknown model id")
    raise                                    # typo in the model string

except anthropic.RateLimitError as e:
    retry_after = int(e.response.headers.get("retry-after", "60"))
    logger.warning("rate limited, retry after %ss", retry_after)
    # retryable

except anthropic.APIStatusError as e:
    if e.status_code >= 500:
        logger.warning("provider error %s", e.status_code)   # retryable
    else:
        raise                                                # your fault

except anthropic.APIConnectionError:
    logger.warning("network problem")        # retryable

except anthropic.APITimeoutError:
    logger.warning("timed out")              # retryable
```

> **Catch a chain, not one broad class.** A single `except Exception` destroys the only
> distinction that matters operationally: **retryable versus not.** Retrying a 400 wastes
> time and never succeeds. Failing hard on a 429 loses a request that would have worked in
> two seconds.

### The SDK already retries

Before you write retry logic, know that the SDK retries connection errors, 408, 409, 429 and
5xx with exponential backoff — **twice by default**.

```python
client = anthropic.Anthropic(max_retries=5)

# Or per-request, without mutating the client:
client.with_options(max_retries=5, timeout=30.0).messages.create(...)
```

Configure that before reaching for the `retry` helper you wrote in Chapter 2. Add your own
layer only when you need behaviour the SDK doesn't provide — a circuit breaker, a fallback to
a different model, or retry budgets shared across a batch.

Be aware that timeouts are retried too, so worst-case wall time is roughly
`timeout × (max_retries + 1)`. Budget accordingly in a request handler.

---

## 6.6 · Thinking and effort

From section 5.9: reasoning tokens are computation you're buying.

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=32_000,
    thinking={"type": "adaptive", "display": "summarized"},
    output_config={"effort": "high"},     # low | medium | high | xhigh | max
    messages=[{"role": "user", "content": "Design a chunking strategy for legal contracts."}],
)
```

**`thinking: {"type": "adaptive"}`** lets the model decide how much to reason per request,
rather than you guessing a fixed budget. The older `budget_tokens` approach is gone on
current models and returns a 400 if you send it — if you've seen that pattern in an older
tutorial, it's stale.

**`display`** controls only whether you *see* the reasoning. Thinking happens and is billed
either way. The default omits it, which looks like a long pause before output appears — so if
you're streaming reasoning to users, set `"summarized"` explicitly.

**`effort`** is the depth dial, and it lives inside `output_config`, not at the top level.

| Effort | Use for |
|---|---|
| `low` | Simple, high-volume, latency-sensitive work |
| `medium` | The cost-saving step down when quality holds |
| `high` | Default. Most real work |
| `xhigh` | Hard coding and agentic tasks |
| `max` | When correctness matters more than cost |

> **Effort is your first quality-versus-cost lever**, and it's a better one than switching to
> a cheaper model: one model means one cache namespace, and caches are model-scoped. Try
> lowering effort before you try downgrading the model — and measure both.

Reasoning blocks arrive in `response.content` with `type == "thinking"`. When continuing a
conversation on the same model, pass them back unchanged.

---

## 6.7 · Prompt caching

A preview — Chapter 9 goes deep — because you'll want it as soon as your prompts get large.

If a large chunk of your prompt is identical across requests (a long system prompt, a
document you're asking many questions about, a fixed set of examples), you can have the
provider cache it. Cached tokens are read at roughly **10%** of normal input price.

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    system=[{
        "type": "text",
        "text": LARGE_STABLE_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }],
    messages=[{"role": "user", "content": question}],
)
```

There's also a simpler top-level form that caches the last cacheable block automatically:

```python
cache_control={"type": "ephemeral"}
```

**The one rule that determines whether caching works:** it is a **prefix match**. The cache
hits only if everything from the start of the request up to the cache marker is byte-identical
to last time. Render order is `tools` → `system` → `messages`.

So: **stable content first, volatile content last.** A timestamp, a request ID, or a
randomly-ordered JSON dump anywhere in the prefix silently destroys every cache hit after it.

Verify rather than assume:

```python
print(response.usage.cache_read_input_tokens)    # zero on repeats = something is invalidating
```

That check has saved people from paying full price for months while believing caching was on.

---

## 6.8 · Concurrency

Chapter 4's patterns, applied.

```python
import asyncio

async def summarize(text: str) -> str:
    response = await async_client.messages.create(
        model="claude-opus-5",
        max_tokens=1_000,
        messages=[{"role": "user", "content": f"Summarize in one sentence:\n\n{text}"}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


# ❌ Sequential. 50 documents × 3s = 150s.
results = [await summarize(d) for d in documents]

# ⚠️ Concurrent but unbounded. 50 simultaneous requests → rate limit wall.
results = await asyncio.gather(*(summarize(d) for d in documents))

# ✅ Bounded. Fast, and stays inside your limits.
sem = asyncio.Semaphore(5)

async def summarize_limited(text: str) -> str:
    async with sem:
        return await summarize(text)

results = await asyncio.gather(*(summarize_limited(d) for d in documents))
```

The `Semaphore` is not optional once you're processing real volume. You'll use this exact
pattern in Part III to embed thousands of chunks without being throttled.

For large offline jobs where latency doesn't matter, there's a better option still: the
Batch API processes asynchronously at roughly **half price**. Worth remembering when you
build your corpus in Chapter 11.

---

## 6.9 · Counting tokens

Before sending an expensive request, you can ask exactly what it will cost in input tokens:

```python
count = client.messages.count_tokens(
    model="claude-opus-5",
    system=system_prompt,
    messages=messages,
)
print(count.input_tokens)
```

**Use this endpoint, not a third-party tokenizer library.** Tokenizers are model-specific; a
library tuned for one model's vocabulary will quietly miscount for another, and you'll build
a budgeting system on wrong numbers.

Two real uses: refusing a request that would blow your context budget before you pay for it,
and checking whether a prompt fits before a long batch job.

---

## 6.10 · Building a conversation

Everything so far, assembled. This is the core of Project B.

```python
"""A minimal conversation manager with cost tracking."""

from dataclasses import dataclass, field

import anthropic

INPUT_PER_MTOK = 5.00
OUTPUT_PER_MTOK = 25.00


@dataclass
class Conversation:
    client: anthropic.Anthropic
    model: str = "claude-opus-5"
    system: str | None = None
    messages: list[dict] = field(default_factory=list)
    total_cost: float = 0.0
    total_input: int = 0
    total_output: int = 0

    def send(self, user_message: str, max_tokens: int = 16_000) -> str:
        self.messages.append({"role": "user", "content": user_message})

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": self.messages,
        }
        if self.system is not None:
            kwargs["system"] = self.system

        response = self.client.messages.create(**kwargs)

        if response.stop_reason == "max_tokens":
            print("⚠️  response truncated — consider raising max_tokens")

        answer = "".join(b.text for b in response.content if b.type == "text")
        self.messages.append({"role": "assistant", "content": answer})
        self._record(response.usage)
        return answer

    def _record(self, usage) -> None:
        self.total_input += usage.input_tokens
        self.total_output += usage.output_tokens
        self.total_cost += (
            usage.input_tokens * INPUT_PER_MTOK
            + usage.cache_read_input_tokens * INPUT_PER_MTOK * 0.1
            + usage.cache_creation_input_tokens * INPUT_PER_MTOK * 1.25
            + usage.output_tokens * OUTPUT_PER_MTOK
        ) / 1_000_000

    @property
    def summary(self) -> str:
        return (
            f"{len(self.messages)} messages · "
            f"{self.total_input:,} in / {self.total_output:,} out · "
            f"${self.total_cost:.4f}"
        )
```

Use it and watch the cost climb:

```python
convo = Conversation(client=anthropic.Anthropic(), system="You are a terse Python tutor.")

print(convo.send("What's a decorator?"))
print(convo.send("Show me one that times a function."))
print(convo.send("Now make it work for async functions."))

print(convo.summary)
```

**Run this and watch the input token count carefully.** Turn 3 resends turns 1 and 2 in full.
Input tokens grow with every exchange, so a long conversation costs quadratically in total,
not linearly. That observation is the entire motivation for Chapter 18's memory strategies —
and for prompt caching, which makes those resent tokens cheap.

---

## 6.11 · Build it

Extend your Chapter 3 project into a CLI assistant. This becomes Project B.

```
src/genai_toolkit/
├── llm/
│   ├── client.py       one shared client, built from Settings
│   ├── conversation.py Conversation with cost tracking
│   ├── streaming.py    async token streaming
│   └── pricing.py      per-model rates and the cost calculation
└── cli/
    └── chat.py         the terminal interface
```

Requirements:

1. **Streaming** — tokens appear as they're generated, never in one block.
2. **Multi-turn** — remembers the conversation.
3. **Cost display** — running total after each turn, and a session summary at exit.
4. **Error handling** — every branch of section 6.5, with sensible retry behaviour.
5. **Configurable** — model, system prompt, temperature/effort from `Settings`.
6. **Commands** — at minimum `/reset`, `/cost`, `/system <text>`, `/model <id>`, `/save`,
   `/quit`.
7. **Graceful Ctrl-C** — interrupting mid-stream stops the generation and returns to the
   prompt without a stack trace.
8. **`make check` passes** — strict types, lint clean, tests green.

**Testing it without spending money** is the interesting engineering problem. Put the client
behind a `Protocol`, write a fake that replays canned responses, and test every path —
streaming, truncation, rate limits, refusals — against the fake. You'll need exactly this
technique for eval suites in Chapter 22, so build it properly now.

```python
from typing import Protocol

class LLMClient(Protocol):
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]: ...
```

### Break it deliberately

1. Set `max_tokens=10` and ask for an essay. Observe `stop_reason == "max_tokens"`.
2. Use a wrong model ID. Read the `NotFoundError`.
3. Unset your API key. Read the `AuthenticationError`.
4. Send 50 concurrent requests with no semaphore. Get rate limited on purpose, then fix it.
5. Have a 20-turn conversation and watch `input_tokens` grow on every turn.
6. Cache a large system prompt, then insert `datetime.now()` into it. Watch
   `cache_read_input_tokens` drop to zero. **This one is the most valuable.**

---

## 6.12 · Exercises

**1 · Parse every block type.** Write `extract(response) -> dict` returning
`{"text": ..., "thinking": ..., "tool_uses": [...]}`. Handle a response with no text blocks
at all without raising.

**2 · A cost ledger.** Log every request to a JSONL file: timestamp, model, input tokens,
output tokens, cached tokens, cost, latency, `stop_reason`. Then write a script that
summarises spend by model and by day. *(You will want this file in Chapter 9.)*

**3 · Measure time to first token.** Instrument a streaming call for TTFT and total time.
Compare across three `effort` settings and three prompt lengths. Explain the pattern you see
using Chapter 5.

**4 · Prove caching works.** Send the same 5,000-token system prompt three times. Log
`cache_creation_input_tokens` and `cache_read_input_tokens` each time. Then break it by
adding a timestamp and show the difference in cost.

**5 · Bounded fan-out.** Summarise 30 documents with `Semaphore(5)`. Compare wall time
against sequential and against unbounded. Handle partial failures with
`gather(..., return_exceptions=True)` so one bad document doesn't lose the other 29.

**6 · A fake client.** Implement the `LLMClient` protocol with a fake that can be scripted to
return text, to truncate, to raise a rate limit error, and to stream slowly. Write tests for
each. *(Chapter 22 depends on this skill.)*

**7 · Conversation trimming.** Extend `Conversation` to keep total input under a token
budget by dropping the oldest turns — always preserving the system prompt and the most recent
exchange. Use `count_tokens` to decide. *(A preview of Chapter 18.)*

**8 · Compare the lineup.** Run the same five prompts across the three models in section 6.2.
Record quality, latency and cost for each. **Write down which one you'd actually ship and
why.** This is the argument you'll make in interviews.

---

## 6.13 · Checkpoint

> **Move on to Chapter 7 when all of these are true.**

**Write from memory:**

1. A streaming async call that yields text and returns final usage.
2. The full error-handling chain, correctly distinguishing retryable from not.
3. A request with adaptive thinking and an effort setting.
4. A cached system prompt, plus the check that proves the cache is being hit.
5. A bounded-concurrency fan-out over a list of inputs.

**Explain, out loud:**

6. Why `response.content[0].text` is a bug waiting to happen.
7. Why input tokens grow every turn, and what that does to the cost of a long conversation.
8. What makes a cached prefix miss, and why order matters.
9. Which errors you retry and which you don't, and why retrying the others is pointless.
10. What `effort` trades off, and why it's usually a better first lever than switching models.

**Verify:**

11. Your CLI streams, tracks cost, survives Ctrl-C, and handles a rate limit gracefully.
12. You have a cost ledger with at least 50 real requests in it.
13. You have deliberately broken your own cache and watched the number change.
14. `make check` is green.

---

## 6.14 · Going deeper (optional)

**Read the Messages API reference end to end.** It's shorter than you'd guess, and you now
have the context to understand all of it. Pay attention to the parameters this chapter
skipped — `stop_sequences`, `metadata`, `service_tier` — so you know they exist when you
need them.

**Look at the raw SSE stream.** Make a streaming request with `curl` and watch the actual
events go by. Chapter 4 taught you the format; seeing a real provider's stream makes it
click, and it demystifies what the SDK is doing for you.

**Read about the Batch API.** Half price, asynchronous, ideal for anything not
latency-sensitive. You'll want it in Chapter 11 when you embed a whole corpus.

**If you're curious about the frontier:** look up extended thinking and effort in the
provider documentation, and read about what "adaptive" actually adapts to. It's the most
actively-moving part of this API.

---

<div align="center">

**[← Chapter 5](../ch05-what-an-llm-is/)** · **[The Book](../../readme.md)** · **[Chapter 7 → Prompting as Engineering](../ch07-prompting-as-engineering/)**

*Chapter 6 of 31 · Week 6*

</div>
