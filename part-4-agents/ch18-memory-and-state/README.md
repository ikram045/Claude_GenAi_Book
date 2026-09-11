# Chapter 18 · Memory & State

### The model remembers nothing. Everything that feels like memory is engineering you do.

> **Week 18 · ~22 hours · Heavy code**
>
> Chapter 17's agent works beautifully for ten iterations and degrades after twenty. This is
> why, and what to do about it.

---

## 18.0 · Why this chapter exists

Section 5.10 stated it plainly: **the API is stateless.** Every request is the model's first
moment of consciousness. Continuity is an illusion you create by resending history.

That illusion has a cost, and the cost compounds:

```
Turn 1     1,000 input tokens
Turn 5     8,000
Turn 10   22,000
Turn 20   58,000
Turn 40  140,000        ← slow, expensive, and approaching the limit
Turn 60      ✗          ← context window exceeded. The conversation is over.
```

And long before the hard limit, quality degrades: attention dilutes across a huge context, and
the important early instruction is now buried in the middle where recall is worst (section
5.11).

So every real system needs a strategy for what to keep, what to compress, what to discard, and
what to store somewhere else and retrieve on demand.

> **The key insight of this chapter:** long-term memory is a **retrieval problem.** Everything
> you learned in Part III — chunking, embedding, hybrid search, reranking, measuring recall —
> applies directly. Memory is RAG over the user's own history.

---

## 18.1 · Four kinds of memory

Borrowed from cognitive science, and genuinely useful as an engineering taxonomy because each
kind needs different machinery.

| Kind | What it holds | Lives in | Lifetime |
|---|---|---|---|
| **Working** | The current conversation | The context window | This request |
| **Episodic** | What happened before — past sessions, events | A database | Forever |
| **Semantic** | Facts about the user and their world | A store you retrieve from | Until contradicted |
| **Procedural** | How to do things — learned patterns, instructions | System prompt, tools, skills | Until you change it |

```
   ┌──────────── THE CONTEXT WINDOW ────────────┐
   │  system prompt         ← procedural        │
   │  retrieved facts       ← semantic          │
   │  session summaries     ← episodic          │
   │  recent messages       ← working           │
   │  the current question                      │
   └────────────────────────────────────────────┘
             ▲                    ▲
             │                    │
      long-term stores    the live conversation
```

Every design decision in this chapter is about which of these four a given piece of information
belongs to, and therefore where it lives.

---

## 18.2 · Working memory: managing the message list

Four strategies, from crude to good. Most systems end up combining several.

### 1 · Sliding window

Keep the last N messages, drop the rest.

```python
def trim_window(messages: list[dict], keep: int = 20) -> list[dict]:
    return messages[-keep:] if len(messages) > keep else messages
```

**Pros:** trivial, fast, free.
**Cons:** the user's name, stated in turn 2, is gone by turn 30. Information loss is total and
silent.

**Two rules if you use it:** never drop the system prompt, and never split a `tool_use` from its
matching `tool_result` — a dangling tool use makes the conversation malformed and the API will
reject it.

```python
def trim_safely(messages: list[dict], budget: int) -> list[dict]:
    """Drop oldest complete exchanges, never splitting a tool_use/tool_result pair."""
    kept: list[dict] = []
    used = 0
    for msg in reversed(messages):
        cost = count_tokens_of(msg)
        if used + cost > budget and kept:
            break
        kept.append(msg)
        used += cost
    kept.reverse()
    return repair_tool_pairs(kept)
```

### 2 · Summarise the old, keep the recent

The workhorse.

```python
async def compress(messages: list[dict], keep_recent: int = 10) -> list[dict]:
    if len(messages) <= keep_recent + 4:
        return messages

    old, recent = messages[:-keep_recent], messages[-keep_recent:]

    summary = await summarise(old)
    return [{"role": "user", "content": f"<earlier_conversation>\n{summary}\n</earlier_conversation>"},
            {"role": "assistant", "content": "Understood. Continuing."},
            *recent]
```

**The summarisation prompt is where the quality is**, and it's worth versioning in your
Chapter 7 library:

```
Summarise this conversation segment for continuing the conversation.

Preserve exactly:
- Facts the user stated about themselves or their situation
- Decisions made and constraints agreed
- Names, numbers, dates, identifiers — verbatim
- Anything the user asked you to remember
- Open questions not yet resolved

Omit:
- Pleasantries and acknowledgements
- Reasoning that led to a stated conclusion
- Content already superseded by later corrections

Write in third person. Be specific. Never generalise a number.
```

That "never generalise a number" line is doing real work. Summaries love to turn *"the refund
window is 14 days"* into *"discussed refund timing,"* which destroys exactly the information you
needed.

### 3 · Server-side compaction

Some APIs handle this for you: as context approaches a threshold, earlier turns are summarised
server-side and replaced with a compaction block.

```python
response = client.beta.messages.create(
    betas=["compact-2026-01-12"],
    model="claude-opus-5",
    max_tokens=16_000,
    messages=messages,
    context_management={"edits": [{"type": "compact_20260112"}]},
)

# CRITICAL: append the full content, not just the text.
messages.append({"role": "assistant", "content": response.content})
```

> **That last line is the trap.** Compaction blocks arrive inside `response.content`, and the
> API needs them on the next request to know what was compacted. Extract only the text string
> and append that, and you **silently lose the compaction state** — the conversation appears to
> work and then behaves strangely. It's a one-line bug with a confusing symptom.

### 4 · Context editing — clear rather than summarise

Distinct from compaction, and often better for agents: **clear** old tool results entirely
rather than summarising them.

```python
response = client.beta.messages.create(
    betas=["context-management-2025-06-27"],
    model="claude-opus-5",
    max_tokens=16_000,
    tools=tools,
    messages=messages,
    context_management={"edits": [
        {"type": "clear_tool_uses_20250919", "clear_tool_inputs": True},
    ]},
)
```

**Why this suits agents specifically:** in a twenty-iteration run, the tool *results* are the
bulk of the context — thousands of tokens of search output, API responses, file contents — and
most of them are no longer needed once the model has extracted what it wanted. Clearing them
reclaims enormous space while leaving the reasoning intact.

| | Compaction | Context editing |
|---|---|---|
| What it does | Summarises history | Removes tool results / thinking |
| Best for | Long conversations | Long agent runs |
| Information | Compressed, retained in gist | **Gone** |

Use editing when the results were consumed; use compaction when the history still matters.

---

## 18.3 · Long-term memory is retrieval

Here's the reframe that makes this tractable.

You cannot keep everything in context. So you store it and **retrieve what's relevant** — which
is exactly Part III, pointed at conversation history instead of documents.

```
   store                                    retrieve
   ─────                                    ────────
   conversation ──▶ extract facts ──▶ DB      query ──▶ search memories
                    ──▶ embed     ──▶ vectors        ──▶ rerank
                                                     ──▶ inject top 3-5
```

### What to store

**Not raw transcripts.** They're verbose, repetitive, and retrieve badly — the same reason you
chunk documents rather than embedding whole files.

**Store extracted facts:**

```python
class Memory(BaseModel):
    # Reasoning first (section 8.6.4)
    reasoning: str = Field(description="Why this is worth remembering long-term.")

    content: str = Field(description="The fact, stated so it makes sense in isolation.")
    kind: Literal["preference", "fact", "decision", "instruction", "context"]
    confidence: Literal["stated", "inferred"] = Field(
        description="'stated' if the user said it explicitly; 'inferred' if you deduced it."
    )
    source_message_id: str
    created_at: datetime
    expires_at: datetime | None = Field(
        description="For time-bounded facts, e.g. 'travelling until March 10'."
    )
```

Two fields worth explaining:

**`confidence: stated | inferred`** — this is not the calibrated-confidence anti-pattern from
section 8.6.7. It's a **verifiable distinction**: either the user said it or they didn't.
Inferred memories are much more likely to be wrong, and you want to be able to weight them
differently or surface them for confirmation.

**`expires_at`** — "I'm travelling until March 10" is true now and misleading in April. Memories
with a natural expiry should have one.

### The extraction step

After each session, or periodically:

```
Review this conversation. Extract facts worth remembering for future
conversations with this user.

Extract:
- Stated preferences ("I prefer Python", "don't use bullet points")
- Durable facts ("I work at Acme", "my project uses Postgres")
- Decisions and constraints agreed
- Explicit instructions ("always check the staging branch first")

Do NOT extract:
- Anything transient ("I'm tired today")
- Anything already stored (you'll be shown existing memories)
- Inferences you're not confident about
- Anything the user would be uncomfortable seeing stored
```

That last line is a genuine design principle, not politeness. **Everything you store is a
liability** — see section 18.6.

### Retrieval and injection

```python
async def build_context(user_id: str, query: str) -> str:
    memories = await memory_store.search(
        user_id=user_id, query=query, k=5, exclude_expired=True
    )
    if not memories:
        return ""
    lines = "\n".join(f"- {m.content}" for m in memories)
    return f"<known_about_user>\n{lines}\n</known_about_user>"
```

**Inject as context, not as instruction.** A memory saying *"user prefers terse answers"* is
information the model should weigh, not a command that overrides your system prompt. If a stored
memory can override your rules, then anything the user says once can permanently reconfigure
your assistant — which is a prompt-injection vector wearing a friendly hat.

### It's RAG, so measure it like RAG

**Chapter 14 applies directly.** Build a gold set of (query, relevant memories) pairs. Measure
recall. A memory system that stores everything and retrieves the wrong things is worse than no
memory at all, because the model now confidently uses irrelevant facts.

---

## 18.4 · The memory tool pattern

Instead of extracting memories behind the model's back, give it a tool and let it manage its own
memory.

```python
{"type": "memory_20250818", "name": "memory"}
```

Or your own equivalent:

```python
@tool
def remember(content: str, kind: str) -> str:
    """Store a fact for future conversations. Use when the user states a durable
    preference, a fact about their situation, or asks you to remember something."""

@tool
def recall(query: str) -> str:
    """Search your memories about this user."""

@tool
def forget(memory_id: str, reason: str) -> str:
    """Remove a memory that is wrong or no longer relevant."""
```

**Advantages:** the model decides what matters, in context. Memory is explicit and auditable. The
user can be shown what was stored.

**Disadvantages:** the model may over-store, under-store, or store wrongly. It costs tool calls.
And it needs clear guidance about what's worth remembering, or you get a memory store full of
"the user said hello."

**In practice, combine:** a tool for explicit "remember this" requests, plus background
extraction for things the user wouldn't think to ask you to store.

---

## 18.5 · State that isn't memory

Not everything an agent needs to persist is a "memory." Conflating these makes systems muddled.

| Kind | Example | Where it lives |
|---|---|---|
| **Task state** | "Step 3 of 7 complete" | A structured object, not prose |
| **Scratchpad** | Intermediate calculations | A file or a tool result |
| **Artifacts** | The document being drafted | A file or a database row |
| **Session config** | Model, effort, persona | Session settings |

```python
@dataclass
class TaskState:
    task_id: str
    goal: str
    steps: list[Step]
    completed: set[str]
    findings: dict[str, str]
    blocked_on: str | None
```

**Keep structured state structured.** Asking the model to track "which steps are done" in prose,
across a long conversation, is asking it to do something it's bad at (counting, state tracking —
section 5.12). Track it in code, and *show* the model the current state each turn:

```
<task_state>
Goal: migrate the auth module to the new session API
Completed: [1] audit current usage · [2] write the adapter
Current: [3] update call sites (14 of 31 done)
Blocked: none
</task_state>
```

Cheap, reliable, and it eliminates a whole class of agent confusion.

---

## 18.6 · The traps

### Memory poisoning

A wrong fact gets stored. It's retrieved forever. The model confidently uses it, and the user
has no idea where it came from.

```
Turn 8:   user mentions a colleague's project deadline
Extracted: "User's project deadline is March 15"     ← wrong subject
Forever:   the assistant plans around a deadline that isn't theirs
```

**Defences:** prefer `stated` over `inferred`; let users view and delete memories; expire
inferred memories faster than stated ones; store the source so a bad memory can be traced.

### Stale memory

Facts change. "I work at Acme" was true two jobs ago.

**Defences:** timestamps on everything, `expires_at` for time-bounded facts, and
**contradiction detection** — when a new memory conflicts with an old one, supersede rather than
accumulate. Two contradictory memories retrieved together is worse than either alone.

### Silent summarisation loss

Turn 40's summary drops the constraint from turn 3, and the agent proceeds happily without it.

**Defences:** a pinned-facts section that is never summarised; explicit "preserve verbatim"
instructions in the summarisation prompt; and **testing your summariser** — take a long
conversation, summarise it, then ask ten questions answerable only from the original. Measure
how many survive.

That test is the single most useful thing in this section, and almost nobody runs it.

### Privacy — the one that has legal consequences

**Everything you store about a user is a liability.** Regulation may give users the right to
see it, correct it, and have it deleted.

Non-negotiables:

- **Never store secrets.** Filter credentials, keys, and card numbers before extraction.
- **Deletion must actually delete** — from the database *and* the vector index. A vector without
  its row is still retrievable content (section 12.7's orphan problem, with a compliance
  dimension).
- **Users must be able to see what's stored.** If you'd be uncomfortable showing them, don't
  store it.
- **Scope memories to the user.** A memory store shared across tenants is a data breach with a
  friendly interface.

### Cross-session context bleed

Memories from a personal conversation surfacing in a work one. Technically correct retrieval,
badly wrong outcome.

**Defence:** scope memories by context, not just by user — workspace, project, or thread. Let
users control the scope.

---

## 18.7 · Build it

**A memory and state layer** for your Chapter 17 agent.

```
src/genai_toolkit/memory/
├── working.py       trimming, tool-pair repair, token budgeting
├── summarise.py     versioned summarisation, with a fidelity test
├── compaction.py    server-side compaction, correctly handled
├── store.py         memory persistence (reuse your Chapter 12 store!)
├── extract.py       post-session fact extraction
├── retrieve.py      memory search — reuse your Chapter 13 pipeline
├── tools.py         remember / recall / forget
└── state.py         structured TaskState
```

Requirements:

1. **Token-budgeted working memory** that never splits a tool pair and never drops the system
   prompt.
2. **Summarisation** with a versioned prompt and a measured fidelity test.
3. **Server-side compaction** handled correctly — full `content` appended.
4. **Context editing** for agent runs, with a measured token saving.
5. **A memory store reusing your Part III infrastructure** — same vector store, same hybrid
   retrieval. **Don't build a second one.**
6. **Extraction** with the `stated`/`inferred` distinction and expiry.
7. **Memory tools** the model can call.
8. **Contradiction detection** that supersedes rather than accumulates.
9. **Structured `TaskState`** rendered into the prompt each turn.
10. **Full user control**: list, view source, delete — with deletion removing the vector too.
11. `make check` green.

### The experiments

**1 · Summarisation fidelity.** Take a 40-turn conversation. Write 15 questions answerable only
from it. Summarise, then ask the 15 questions against the summary. **Report the percentage that
survive.** Then improve the prompt and measure again. This is the most valuable experiment in
the chapter.

**2 · The strategy comparison.** Run a 60-turn conversation under: no management (until it
breaks), sliding window, summarisation, and compaction. Measure at each: token count, cost, and
how many of your 15 questions are still answerable.

**3 · Context editing on an agent run.** Take a 20-iteration agent task. Measure total tokens
with and without tool-result clearing. **The saving is usually dramatic.**

**4 · Memory retrieval quality.** Build a gold set of 30 (query, relevant memories) pairs.
Measure recall@5. **Yes, this is Chapter 14 again — that's the point.**

**5 · Poison it.** Deliberately store a wrong inferred fact. Have three conversations. Observe
how it propagates. Then implement contradiction detection and try again.

**6 · The pinned-facts test.** Put a hard constraint in turn 2 ("never suggest solutions
involving MongoDB"). Run 50 turns with summarisation. Does the constraint survive? Implement
pinning and retest.

**7 · Deletion audit.** Delete a memory. Then search for its content directly in the vector
index. **Is it actually gone?** If not, you have a compliance bug.

---

## 18.8 · Exercises

**1 · Safe trimming.** Implement trimming that respects a token budget, preserves the system
prompt, and never splits a tool pair. Test with an agent history full of tool calls.

**2 · Summariser versions.** Write three summarisation prompts of increasing specificity.
Measure fidelity for each. Version the winner with a changelog entry (section 7.12).

**3 · Extraction precision.** Run extraction over 20 conversations. Manually label each extracted
memory as correct, wrong, or not-worth-storing. **Report precision.** Tune the prompt and
re-measure.

**4 · Expiry logic.** Implement `expires_at`. Find five fact types that need it and five that
don't. Write the rule that distinguishes them.

**5 · Contradiction detection.** When a new memory contradicts an existing one, decide which
wins. Implement it. Test with: a corrected fact, a changed preference, and a genuine ambiguity.

**6 · Memory cost.** Measure the token cost of injecting 5 memories per request, across 1,000
requests. Compare against the value. **Is your memory system worth what it costs?**

**7 · State rendering.** Build `TaskState` and render it into the prompt each turn. Compare agent
accuracy on a 7-step task with and without it.

**8 · A user-facing memory page.** List every memory, its source, when it was created, and a
delete button. Use it on your own data. **You will delete things, and that tells you something
about your extraction prompt.**

---

## 18.9 · Checkpoint

> **Move on to Chapter 19 when all of these are true.**

**Explain, out loud:**

1. Why conversations cost more per turn as they grow, and what shape that curve is.
2. The four kinds of memory and where each one lives.
3. Why long-term memory is a retrieval problem, and what that lets you reuse.
4. The difference between compaction and context editing, and when each fits.
5. Why appending only the text of a compacted response is a silent bug.
6. Why memories should be injected as context rather than as instructions.
7. Three ways memory gets poisoned, and a defence for each.
8. Why deletion must remove the vector as well as the row.

**Write from memory:**

9. Token-budgeted trimming that preserves tool pairs.
10. A summarisation prompt with explicit preserve/omit lists.
11. A `Memory` model with the `stated`/`inferred` distinction and expiry.
12. Memory injection as a delimited context block.

**Verify:**

13. Your summariser's fidelity is a measured number.
14. Your memory retrieval recall is a measured number.
15. Context editing's token saving on an agent run is a measured number.
16. Deleting a memory removes it from the vector index, verified by searching for it.

Three of those four checks are numbers. That's not an accident — this is the chapter where
people build systems on intuition and never find out that their summariser drops 40% of the
facts.

---

## 18.10 · Going deeper (optional)

**Read the context-management documentation** for your provider — compaction and context editing
both. The exact semantics of what's preserved and what's discarded matter, and they're not
guessable.

**Read about agent memory architectures.** Several research systems formalise the four-type
taxonomy from section 18.1. Useful vocabulary, and the designs are worth stealing from.

**If you want the hard problem:** search for work on knowledge conflict and belief revision in
LLM systems. Deciding which of two contradictory facts wins is genuinely unsolved, and knowing
that stops you expecting a clean answer.

**If you want the practical angle:** look at how consumer AI assistants expose memory to users —
what they show, what they let you edit, how they scope it. The UX decisions encode a lot of
hard-won engineering.

---

<div align="center">

**[← Chapter 17](../ch17-the-agent-loop/)** · **[The Book](../../readme.md)** · **[Chapter 19 → MCP](../ch19-mcp/)**

*Chapter 18 of 31 · Week 18*

</div>
