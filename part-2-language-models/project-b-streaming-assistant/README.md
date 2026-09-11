# 🔨 Project B · The Streaming Assistant

### Week 9 · ~22 hours · The first thing you build that you'll actually use every day

---

## The brief

Build a **terminal AI assistant** that you genuinely use — not a demo, a tool. It streams,
remembers, tracks what it costs you, survives being interrupted, and is tested without
spending a cent.

The selection criterion for every feature below is the same: **would you still be using this
in three months?** If a feature doesn't serve that, it's not in the brief.

This is your first project with a model in it. It's deliberately a CLI rather than a web app,
for three reasons: the interface work won't distract from the engineering, a terminal tool is
something you'll actually reach for daily, and every component you build here reappears
—unchanged in shape — inside Project C and Project D.

---

## Why a CLI and not a chatbot web app

You could build a chat UI this week. Don't, yet.

A web chat app spreads your effort across frontend state, WebSocket plumbing, and CSS, and
the model layer ends up being the thinnest part of it. A CLI puts 100% of your attention on
the part that's new: streaming, conversation state, cost accounting, error recovery, and
testability.

There's also a practical argument. You will use a terminal assistant. You will not use your
own worse version of a chat website. **Tools you use get improved; demos get abandoned.**

---

## Requirements

### Core behaviour

**1 · Streaming, always**
Tokens appear as generated. Never a spinner followed by a wall of text. Measure and display
time to first token.

**2 · Multi-turn conversation**
Full history sent each turn. When history approaches a configured token budget, trim the
oldest exchanges — always preserving the system prompt and the most recent turn.

**3 · Cost tracking, visible**
After each response, a one-line summary: tokens in/out, cached tokens, cost of that turn, and
running session total. On exit, a session report.

**4 · Commands**

| Command | Behaviour |
|---|---|
| `/help` | List commands |
| `/reset` | Clear the conversation, keep the system prompt |
| `/system <text>` | Replace the system prompt (and reset) |
| `/model <id>` | Switch model mid-session; report the price change |
| `/effort <level>` | `low` … `max` |
| `/cost` | Detailed session breakdown |
| `/tokens` | Current context usage against the budget |
| `/save [file]` | Write the transcript to markdown |
| `/load <file>` | Resume a saved conversation |
| `/retry` | Re-run the last user message |
| `/quit` | Session report, then exit |

**5 · Graceful interruption**
Ctrl-C mid-stream stops generation, keeps the partial response in history, and returns to the
prompt. No stack trace. Ctrl-C at an empty prompt exits cleanly with the session report.

**6 · Real error handling**
Every branch from section 6.5. Rate limits back off and inform the user rather than crashing.
Auth errors fail immediately with an actionable message. `stop_reason == "max_tokens"` warns
visibly.

**7 · Prompt caching**
The system prompt and any few-shot examples are cached. **Display the cache hit rate** — you
should be able to watch it work.

**8 · Configuration**
Everything from `Settings`: model, system prompt, effort, token budget, whether to show
reasoning. Nothing hardcoded.

### Quality bar

| Requirement | Verified by |
|---|---|
| `mypy --strict` clean | `make type` |
| ruff clean and formatted | `make lint` |
| Coverage ≥ 85% with meaningful assertions | `make test` |
| **Zero API calls in the test suite** | Tests pass offline |
| Every error path tested | Read your test file |
| Every request written to the ledger | `--report` on real data |

---

## Suggested structure

```
src/assistant/
├── __init__.py
├── config.py              Settings
├── llm/
│   ├── protocol.py        LLMClient Protocol ← the key abstraction
│   ├── anthropic.py       the real implementation
│   ├── fake.py            scriptable test double
│   └── pricing.py         rates and cost calculation
├── conversation/
│   ├── state.py           messages, system prompt, trimming
│   └── transcript.py      save / load markdown
├── metering/
│   ├── ledger.py          append-only JSONL
│   └── report.py          aggregation and printing
├── cli/
│   ├── app.py             the REPL
│   ├── commands.py        command dispatch
│   └── render.py          streaming output, colours, status line
└── errors.py
tests/
├── conftest.py
├── test_conversation.py   trimming, state, edge cases
├── test_pricing.py        cost arithmetic
├── test_commands.py       every command
├── test_streaming.py      against the fake
├── test_errors.py         every failure path
└── test_ledger.py
```

### The design decision that matters most

```python
from collections.abc import AsyncIterator
from typing import Protocol


class LLMClient(Protocol):
    async def stream(
        self, *, messages: list[dict], system: str | None, **kwargs
    ) -> AsyncIterator[StreamEvent]: ...
```

Everything above this protocol is testable without a network. Everything below it is one
small, well-understood adapter.

Your `FakeClient` should be **scriptable** — able to emit a canned response, stream slowly,
truncate at `max_tokens`, raise a rate limit error, raise a connection error, and return a
refusal. Build it early; it makes every subsequent test trivial.

> **This exact technique is how you'll build eval suites in Chapter 22.** You're not writing
> throwaway test scaffolding — you're learning the pattern that makes the most important
> chapter in the book possible.

---

## Acceptance criteria

**Behaviour**
- [ ] Tokens appear progressively; TTFT displayed and under 2s for a short prompt
- [ ] A 20-turn conversation stays coherent
- [ ] Trimming keeps the context under budget without losing the system prompt
- [ ] Every command works, including `/load` on a file saved by `/save`
- [ ] `/retry` re-runs the last message without duplicating history
- [ ] Ctrl-C mid-stream returns to the prompt with the partial response retained

**Correctness**
- [ ] Session cost matches a hand-calculation from the ledger to the cent
- [ ] Cache hit rate is non-zero after the second turn
- [ ] `stop_reason == "max_tokens"` produces a visible warning
- [ ] Switching models mid-session reports the new rates and resets cache expectations
- [ ] Empty input, whitespace-only input, and a 50,000-word paste are all handled

**Robustness**
- [ ] Rate limit → backs off, informs the user, succeeds on retry
- [ ] Missing API key → clear message, exit code 1, no traceback
- [ ] Network failure mid-stream → partial response kept, error explained
- [ ] Malformed `/load` file → error, session continues

**Quality**
- [ ] `make check` green
- [ ] Test suite passes with **no network access**
- [ ] Every `# type: ignore` justified in a comment
- [ ] No secrets in the repo or in the ledger

---

## Stretch goals

After everything above is green. Each one previews a later chapter:

1. **Pipe support.** `cat error.log | assistant "what caused this?"`. Turns the tool into part
   of your shell workflow and roughly triples how often you use it.
2. **Named system prompts.** `/persona reviewer` loads from your Chapter 7 prompt library —
   versioned prompts, in the tool you use daily.
3. **Cost dashboard.** `assistant --report --since 7d` with spend by day, model, and persona.
4. **Response cache.** Hash of (model, system, messages) → response. Watch repeated questions
   become free. *(Section 9.5.)*
5. **Model comparison.** `/compare "question"` runs the same prompt on two models side by side
   with cost and latency for each. **This is a mini-eval harness** — Chapter 22 in embryo.
6. **Structured mode.** `/extract <schema.py>` uses Chapter 8's constrained output to return
   typed data instead of prose.
7. **A Flutter client.** Same backend, mobile front end, streaming over SSE. Your edge, in
   week 9.

---

## How to present it

### The README must answer

1. **What it is** — two sentences.
2. **Quickstart** — install to first response in under three minutes.
3. **A screenshot or asciinema recording.** Streaming and a cost line, visible. This is worth
   more than three paragraphs of description, because it proves it's real.
4. **Design decisions** — why a Protocol boundary, why JSONL for the ledger, how trimming
   decides what to drop.
5. **Cost analysis** — your own usage data. *"200 conversations, 1,340 requests, $4.12, 61%
   cache hit rate, p95 TTFT 780ms."* Real numbers from a tool you actually used.
6. **What I'd do differently.**

### Interview questions you should be ready for

> **"How do you test code that calls a non-deterministic API?"**
> The Protocol boundary and the scriptable fake. Walk through how you test a rate limit
> without being rate limited.

> **"What does a conversation cost, and why does it grow?"**
> Show the ledger. Explain quadratic growth from resending history, and how caching and
> trimming address it.

> **"Show me you understand caching."**
> The cache hit rate in your report, and the story of breaking it with a timestamp.

---

## Before you start

**Build the fake client first.** Before the real one. It forces the Protocol boundary to be
right, and it means you can develop the entire CLI — streaming, commands, trimming, error
paths — without spending money or waiting on the network. Most people do this backwards and
end up with untestable code welded to an SDK.

**Use it for a week before you call it done.** You'll find five things that annoy you, and
fixing those five is what turns a project into a tool.

**Timebox to 22 hours.** If you're at hour thirty adding syntax highlighting, stop. Ship it,
write the README, start Chapter 10. Part III is the most important part of this book and it
needs you fresh.

---

<div align="center">

**[← Chapter 9](../ch09-context-cost-latency/)** · **[The Book](../../readme.md)** · **[Chapter 10 → Embeddings, Deeply](../../part-3-retrieval/ch10-embeddings-deeply/)**

*End of Part II · Week 9 of 34*

</div>
