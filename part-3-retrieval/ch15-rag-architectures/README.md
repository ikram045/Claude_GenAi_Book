# Chapter 15 · RAG Architectures & Failure Modes

### The generation half, eight ways it breaks, and when not to use RAG at all

> **Week 14 · ~22 hours · Synthesis**
>
> Chapters 10–14 built retrieval. This chapter is what happens after the chunks come back —
> and a diagnostic catalogue you'll return to every time a RAG system misbehaves.

---

## 15.0 · Why this chapter exists

You can now retrieve well and prove it. But retrieval is half a system. The other half is
turning retrieved chunks into a trustworthy answer, and it has its own failure modes that no
amount of recall will fix.

More importantly: when a RAG system gives a bad answer, **there are eight distinct things that
could have gone wrong**, they need eight different fixes, and without a systematic way to tell
them apart you'll guess. Guessing at a probabilistic system is how people spend three weeks
tuning prompts to fix a chunking bug.

This chapter gives you the map.

---

## 15.1 · The generation half

```
   retrieved chunks
         │
   ┌─────▼──────────┐
   │ CONSOLIDATION  │  dedupe · order · budget · resolve conflicts
   └─────┬──────────┘
   ┌─────▼──────────┐
   │ PROMPT ASSEMBLY│  system rules · context · question (last)
   └─────┬──────────┘
   ┌─────▼──────────┐
   │   GENERATION   │
   └─────┬──────────┘
   ┌─────▼──────────┐
   │  POST-CHECK    │  citations valid? grounded? refused correctly?
   └─────┬──────────┘
         ▼
       answer
```

Consolidation and post-checking are the two stages people skip, and they're where a
surprising amount of quality lives.

---

## 15.2 · The answer prompt

Chapter 7's principles, applied to the specific job of answering from context.

```python
SYSTEM = """You answer questions using only the provided documents.

Rules:
- Answer only from the documents. Never use general knowledge to fill gaps.
- Every factual claim must cite its source as [1], [2], etc.
- If the documents don't contain the answer, respond exactly:
  INSUFFICIENT_CONTEXT: <what information would be needed>
- If documents disagree, say so explicitly and cite both.
- Quote exact figures, dates and names from the documents. Never approximate.

Format: 2-4 sentences unless the question requires more. No preamble."""


USER_TEMPLATE = """<documents>
{numbered_chunks}
</documents>

<question>
{question}
</question>"""
```

Five things are doing real work here, and each maps to something you've already learned:

**"Only from the documents"** — the strongest available anti-hallucination instruction, because
it converts the task from recall (weak, section 5.12) to copying (strong).

**Citations** — force grounding and make fabrication *visible*. Section 15.3.

**`INSUFFICIENT_CONTEXT`** — from section 7.10. Creates a path that competes with improvising,
and gives you a machine-detectable signal.

**Conflict handling** — real corpora contain contradictions. Without this instruction the model
silently picks one, and you never learn there was a conflict.

**The question last** — lost-in-the-middle (section 5.11). This is free and it matters.

### Numbering the chunks

```python
def format_chunks(chunks: list[Chunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        heading = " → ".join(c.heading_path) if c.heading_path else ""
        parts.append(
            f"[{i}] Source: {c.document_title}"
            + (f", section: {heading}" if heading else "")
            + (f" (updated {c.updated_at:%B %Y})" if c.updated_at else "")
            + f"\n{c.display_text}"
        )
    return "\n\n".join(parts)
```

Including the date is not decoration — it lets the model reason about which of two conflicting
documents is current, which is the Chapter 1 bug handled at the prompt level as well as the
filter level.

---

## 15.3 · Citations

Citations are the most important trust mechanism in a RAG system, and most implementations get
them wrong in the same way: they ask for citations and then never check them.

**A model can hallucinate a citation.** `[3]` when chunk 3 says nothing of the sort. The
citation makes the answer *look* grounded while being exactly as ungrounded as before — which
is worse than no citation, because it manufactures false confidence.

### Verify them

```python
@dataclass
class CitationCheck:
    valid_indices: bool          # every [n] refers to a chunk that exists
    all_claims_cited: bool       # no uncited factual sentences
    supported: dict[int, bool]   # does the cited chunk actually support the claim?


def check_indices(answer: str, n_chunks: int) -> tuple[bool, list[int]]:
    cited = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    invalid = [c for c in cited if not 1 <= c <= n_chunks]
    return not invalid, invalid
```

Index validity is free and catches the crudest failures. Support verification is harder — it
means checking whether the cited chunk genuinely backs the claim. Two approaches:

1. **String overlap.** If the answer quotes a figure, check that figure appears in the cited
   chunk. Cheap, catches a lot, and completely deterministic.
2. **An LLM judge.** *"Does this chunk support this claim? yes/no."* More thorough, costs a
   call. This is Chapter 22's technique.

> **Do at least the cheap check, on every response, in production.** An invalid citation index
> is a bug you can detect in microseconds, and shipping without that check means shipping a
> system that can confidently cite chunk 7 of a 5-chunk context.

---

## 15.4 · Architectures

Five shapes, increasing in capability and cost. **Move up only when measurement demands it.**

### 1 · Naive RAG

```
query → embed → vector search top-k → stuff into prompt → answer
```

The tutorial version. A fine baseline, and the thing every number in Chapter 14 is measured
against.

### 2 · Advanced RAG — what you built

```
query → rewrite → [vector ∥ BM25 ∥ HyDE] → RRF → rerank → consolidate → answer → verify
```

Chapters 11–14. **This is the right default for the large majority of systems**, and most teams
never need to go further.

### 3 · Routed RAG

Not every question needs the same treatment.

```
                    ┌─▶ identifier lookup  → BM25 only, skip the pipeline
    query → route ──┼─▶ document Q&A       → the full pipeline
                    ├─▶ aggregation        → SQL over metadata, not retrieval
                    └─▶ chitchat           → no retrieval at all
```

Cheap, fast, and it fixes a category of failure that tuning retrieval never will — because
*"how many support tickets did we close last month?"* is not a retrieval question and no amount
of recall will make it one.

Route with a small classification call or, where possible, with heuristics (a regex for
identifier-shaped queries costs nothing).

### 4 · Agentic RAG

The model decides what to search for, reads results, and searches again.

```
   model ──▶ search("refund policy enterprise")
         ◀── results
   model ──▶ "not enough — need the exception clause"
         ──▶ search("refund exceptions annual contracts")
         ◀── results
   model ──▶ answer
```

**Genuinely better for multi-hop questions** — ones where you can't know the second query until
you've seen the first result.

**Genuinely more expensive**: several model calls per question, higher latency, and a new
failure mode where the agent loops without converging. This is Part IV's territory, and section
17 covers loop control.

**Adopt it when your failure log (section 14.5) shows multi-hop failures dominating.** Not
before.

### 5 · Graph RAG

Extract entities and relationships into a knowledge graph; traverse it to assemble context.

Powerful for questions about *connections* — "which suppliers are affected by the port closure,
and which of our products do they serve?" — that no amount of chunk retrieval answers, because
the answer is a path, not a passage.

Expensive to build and maintain. **Consider it only when your questions are genuinely
relational**, and know that you're taking on an extraction pipeline as well as a retrieval one.

> **The progression discipline:** each step up adds latency, cost and failure modes. Your
> failure log tells you when to climb. Architecture chosen from a blog post rather than from
> measurement is how systems get complicated without getting better.

---

## 15.5 · The eight failure modes

**The centrepiece of this chapter.** When a RAG system gives a bad answer, it's one of these.
Learn to diagnose by symptom.

### 1 · Missing content

**Symptom:** Correct refusal, or a confident answer about something your corpus never covered.
**Cause:** The information isn't in your documents at all.
**Diagnosis:** Search the raw source files by hand. Is it there?
**Fix:** Not a retrieval problem. Add the content, or route the question elsewhere.

> **This is the most under-diagnosed failure.** Teams spend weeks tuning retrieval for questions
> their corpus simply cannot answer. Every `INSUFFICIENT_CONTEXT` response is a data point about
> a content gap — log them and review them, because that list is often more valuable than
> another tuning iteration.

### 2 · Missed by retrieval

**Symptom:** The answer exists in a chunk, and the chunk wasn't retrieved.
**Diagnosis:** Search for the chunk directly. Is it in the top 50? The top 200?
**Fix:** Depends on *why* — exact term → BM25 weight (13.1); vague query → rewriting (13.4);
asymmetry → HyDE (13.5); ANN miss → raise `ef_search` (12.3).

### 3 · Retrieved but ranked too low

**Symptom:** The right chunk is at rank 23; you sent the top 5.
**Diagnosis:** Compare recall@50 against recall@5. A large gap means a ranking problem.
**Fix:** Reranking (13.3). This is precisely what it's for, and it's usually the largest
single win available.

### 4 · Lost in consolidation

**Symptom:** The chunk was in the top 5 and never reached the model.
**Cause:** Token budget truncation, aggressive deduplication, or a filter applied too late.
**Diagnosis:** **Log the final assembled prompt.** Is the chunk in it?
**Fix:** Section 15.6. This failure is invisible unless you log the prompt, which is why you
must.

### 5 · Present but not extracted

**Symptom:** The answer is demonstrably in the context, and the model didn't use it.
**Causes:** Buried in the middle of a long context (5.11); contradicted by another chunk;
phrased in a way the model didn't connect to the question; too many distractor chunks.
**Fix:** Send fewer, better chunks — which reranking enables. Put the question last. Try
`effort` higher. **This failure is the strongest argument for precision over recall in the final
selection.**

### 6 · Wrong specificity

**Symptom:** Answer is technically right and practically useless — too vague, or drowning in
detail.
**Cause:** Prompt doesn't specify the expected level; retrieved chunks are at the wrong
granularity.
**Fix:** Chapter 7 specificity, and chunk size (11.4).

### 7 · Incomplete

**Symptom:** Answers part of a multi-part question and stops.
**Cause:** Retrieval satisfied one sub-question; or the model stopped early.
**Fix:** Query decomposition (13.4), or agentic RAG (15.4) for genuine multi-hop.

### 8 · Stale or conflicting

**Symptom:** Cites an outdated policy; or two chunks disagree and the model silently picks one.
**Cause:** Multiple document versions indexed; no recency signal; no conflict handling.
**Fix:** Version metadata and filters (11.7, 12.6); dates in the formatted context (15.2); an
explicit conflict instruction in the prompt; deduplication at ingestion (11.3).

> **This is the Chapter 1 bug** — the 2023 parental leave policy outscoring the 2025 one. It is
> a four-layer problem, and it needs fixes at ingestion, indexing, prompting *and* monitoring.
> Single-layer fixes leave it half-solved.

### The diagnostic table

Pin this up.

| # | Failure | Fastest diagnostic | Primary fix |
|:---:|---|---|---|
| 1 | Missing content | Grep the source files | Add content |
| 2 | Missed by retrieval | Is it in top 200? | Hybrid / rewriting / HyDE |
| 3 | Ranked too low | recall@50 vs recall@5 | **Reranking** |
| 4 | Lost in consolidation | **Log the final prompt** | Budget and dedupe logic |
| 5 | Not extracted | Read the prompt — is it there? | Fewer, better chunks |
| 6 | Wrong specificity | Read the answer | Prompt + chunk size |
| 7 | Incomplete | Count the sub-questions | Decomposition / agentic |
| 8 | Stale or conflicting | Check chunk dates | Versioning, filters, prompt |

**Log the final assembled prompt on every request.** Three of the eight diagnostics start there,
and without it you're debugging blind.

---

## 15.6 · Consolidation

The stage between retrieval and generation, and the home of failure mode 4.

```python
def consolidate(
    results: list[RetrievalResult], token_budget: int = 6_000
) -> list[Chunk]:
    """Deduplicate, order and budget the retrieved chunks."""
    seen_hashes: set[str] = set()
    selected: list[Chunk] = []
    used = 0

    for r in results:                       # already in relevance order
        if r.chunk.content_hash in seen_hashes:
            continue
        if used + r.chunk.token_count > token_budget:
            continue                        # skip, don't break — a later chunk may fit
        seen_hashes.add(r.chunk.content_hash)
        selected.append(r.chunk)
        used += r.chunk.token_count

    return reorder_for_attention(selected)
```

Four decisions in fifteen lines:

**Deduplication.** Overlapping chunks (11.6) produce near-identical text. Duplicates waste budget
and add no information.

**`continue`, not `break`.** If chunk 3 is huge and doesn't fit, chunk 4 might. Breaking on the
first overflow silently drops everything after a single large chunk — a classic instance of
failure mode 4.

**Budget.** Fewer chunks is often better (5.11, 15.5 #5). Don't fill the budget because you can.

**Reordering.** From lost-in-the-middle: put the most relevant chunks at the **start and end**,
weakest in the middle.

```python
def reorder_for_attention(chunks: list[Chunk]) -> list[Chunk]:
    """Most relevant at the edges, least in the middle."""
    out: deque[Chunk] = deque()
    for i, c in enumerate(chunks):          # chunks arrive best-first
        (out.appendleft if i % 2 else out.append)(c)
    return list(out)
```

Cheap, and it measurably helps on long contexts.

### Expanding to neighbours

Sometimes the retrieved chunk is right but slightly too small. Because you stored `char_start`
and `char_end` (11.7), you can widen it:

```python
expanded = document_text[max(0, c.char_start - 500) : c.char_end + 500]
```

Retrieve on small precise chunks; *present* larger ones. This gets you precision in search and
context in generation — the section 11.4 tradeoff, dissolved.

---

## 15.7 · Handling "no answer"

A RAG system that always produces an answer is a RAG system that lies when it doesn't know.

```python
if answer.startswith("INSUFFICIENT_CONTEXT:"):
    needed = answer.removeprefix("INSUFFICIENT_CONTEXT:").strip()
    logger.info("content gap: query=%r needed=%r", query, needed)
    await content_gaps.record(query, needed)
    return NoAnswer(reason=needed, suggestion=escalation_path(query))
```

Do three things with it:

1. **Tell the user honestly**, and offer a path — escalate, search elsewhere, rephrase.
2. **Log it as a content gap.** This list is your corpus roadmap and it's more actionable than
   most tuning.
3. **Track the refusal rate.** It's a health metric with two failure directions: a rising rate
   means retrieval is degrading or questions have drifted; a rate near zero means the model
   isn't refusing when it should, which is worse.

Retrieval scores give you a second, cheaper signal:

```python
if not results or results[0].rerank_score < CALIBRATED_THRESHOLD:
    return NoAnswer(reason="no sufficiently relevant documents")
```

Note **calibrated** — from section 10.3, a threshold you haven't measured on your own data with
your own model is a guess. Derive it from your gold set.

---

## 15.8 · When not to use RAG

Retrieval is a hammer, and several common requests are not nails. Recognising these saves
enormous effort.

| The question | Why RAG fails | Use instead |
|---|---|---|
| "How many tickets did we close last month?" | Aggregation over all records; retrieval returns *some* chunks | SQL, via a tool (Part IV) |
| "Summarise this 40-page document" | You need all of it, not the relevant parts | Put the whole document in context |
| "What's our largest customer by revenue?" | Ranking over a full dataset | A database query |
| "What's the weather in Mumbai?" | Not in any corpus; changes constantly | An API tool |
| "Compare every version of this policy" | Needs exhaustive coverage | Fetch all versions by metadata |
| *Corpus under ~50 pages* | Retrieval adds failure modes for no benefit | Put it all in the context window |

That last row deserves emphasis. **If your entire corpus fits comfortably in a context window,
don't build RAG.** Send the whole thing, cache it (section 9.4 — a large stable prefix is the
ideal caching workload), and skip four chapters of machinery. People build elaborate retrieval
pipelines over 30 documents, and it's both slower and worse.

> **The general rule:** RAG answers *"find me the relevant passage."* It does not answer
> *"compute something over all my data."* The second is a database question, and the right
> response is to give the model a database tool — which is Part IV.

---

## 15.9 · Build it

**The complete RAG system.** Everything from Chapters 10–15, assembled. This *is* Project C's
core.

```
src/genai_toolkit/rag/
├── consolidate.py   dedupe, budget, reorder, expand to neighbours
├── prompt.py        versioned answer prompts (Chapter 7's library)
├── generate.py      the answering call, streaming
├── citations.py     extraction, index validation, support checking
├── gaps.py          content-gap logging and reporting
├── router.py        query routing (15.4 #3)
└── pipeline.py      end to end, fully instrumented
```

Requirements:

1. **End to end**: question → route → retrieve → rerank → consolidate → generate → verify.
2. **Citations required and verified.** Index validity always; support checking configurable.
3. **`INSUFFICIENT_CONTEXT` handled** — surfaced to the user, logged as a content gap.
4. **Conflict detection** — when retrieved chunks disagree, the answer must say so.
5. **The final assembled prompt logged** on every request. Non-negotiable (failure mode 4).
6. **A trace per request**: which retrievers fired, what was retrieved, what survived
   consolidation, what was cited, latency per stage, cost.
7. **Streaming**, using Chapter 6's async generator and Chapter 4's SSE endpoint.
8. **Graceful degradation** at every stage — reranker down, model rate-limited, store slow.
9. `make check` green.

### The diagnostic exercise

**Take 20 failing queries from your Chapter 14 failure log and classify each into one of the
eight modes.** Then:

- Count the modes. Which dominates?
- Fix the top one.
- Re-measure.
- Reclassify.

Write it up:

```
Failure mode distribution, n=20 (baseline)
  3 · ranked too low          8   ← fix this first
  2 · missed by retrieval     4
  1 · missing content         3   ← content gap, not an engineering problem
  8 · stale/conflicting       2
  5 · not extracted           2
  7 · incomplete              1

After adding reranking:
  3 · ranked too low          1
  ...
```

That progression — categorise, fix the biggest, re-measure — **is the job.** It's also the
clearest possible demonstration that you engineer rather than tinker.

### Break it deliberately

1. Ask something your corpus definitely doesn't cover. Does it refuse, or invent? Make it
   refuse.
2. Index two contradictory documents. Ask about them. Does the answer acknowledge the conflict?
3. Force a citation to a non-existent chunk (shrink the context after generation). Does your
   verifier catch it?
4. Set the token budget so low that the top chunk doesn't fit. Watch failure mode 4. Then fix
   the `break`/`continue` bug if you have it.
5. Put the answer chunk in the exact middle of 20 chunks. Compare against putting it first.
   Measure the difference. **Then implement reordering and measure again.**
6. Ask an aggregation question ("how many..."). Observe it fail, then route it away.

---

## 15.10 · Exercises

**1 · Citation verifier.** Implement index validation and string-overlap support checking. Run
over 50 answers. **Report the rate of invalid and unsupported citations.** Most people are
surprised.

**2 · Conflict test set.** Construct 10 query/document sets with genuine contradictions. Measure
how often the answer acknowledges the conflict, with and without the prompt instruction.

**3 · The middle-of-context experiment.** Place the answer chunk at positions 1, 5, 10, 15 and
20 of a 20-chunk context. Measure answer accuracy at each. **Plot it.** This is section 5.11,
measured on your own system.

**4 · Refusal calibration.** Build 20 answerable and 20 unanswerable queries. Measure the false-
refusal rate and the false-answer rate. Tune the threshold and the prompt to balance them.
Decide which error you'd rather make, and justify it.

**5 · Neighbour expansion.** Implement it. Measure answer quality at expansions of 0, 250, 500
and 1,000 characters. Find where extra context stops helping and starts diluting.

**6 · Router.** Classify queries into four types and route accordingly. Measure latency and cost
savings on the cheap routes, and confirm quality holds.

**7 · Multi-hop.** Build 10 questions requiring two retrieval steps. Measure single-shot RAG
against decomposition against a simple agentic loop. Report quality, latency and cost for all
three. *(This is the argument for Part IV, made with your own data.)*

**8 · Content-gap report.** Run 100 realistic queries. Collect every `INSUFFICIENT_CONTEXT`.
Cluster them. **Produce a prioritised list of documents your corpus is missing.** Give it to
whoever owns the content.

---

## 15.11 · Checkpoint

> **Move on to Project C when all of these are true.**

**Recite, from memory:**

1. **All eight failure modes, with the fastest diagnostic for each.** This is the chapter.

**Explain, out loud:**

2. Why a citation you don't verify is worse than no citation.
3. Why `continue` rather than `break` in the consolidation loop.
4. Why reordering chunks for attention helps, and where the weakest chunks go.
5. Why the five architectures are a ladder you climb on evidence.
6. Four kinds of question RAG is the wrong tool for, and the right tool for each.
7. Why a corpus under ~50 pages probably shouldn't use RAG at all.
8. Why every `INSUFFICIENT_CONTEXT` is valuable rather than a failure.

**Verify:**

9. Your system cites, and verifies its own citations.
10. It refuses when it should, and logs the gap.
11. It detects and reports conflicts between sources.
12. The final assembled prompt is logged on every request.
13. You have classified 20 real failures into the eight modes and fixed the top one.
14. You have measured the position-in-context effect yourself.

Number 1 and number 13 together are what turn "I built a RAG system" into "I can debug a RAG
system," which is a very different sentence in an interview.

---

## 15.12 · Going deeper (optional)

**Read "Seven Failure Points When Engineering a RAG System."** A short paper cataloguing real
production failures across several systems. Section 15.5 is a descendant of it, and reading the
original case studies makes the categories concrete.

**Read about self-RAG and corrective RAG.** Approaches where the system evaluates its own
retrieval and decides whether to search again. They're the bridge between this chapter and
Part IV.

**If your questions are relational:** read about GraphRAG implementations. Understand the
maintenance cost before you commit — the extraction pipeline is a system of its own.

**If you want the counter-argument:** search for critiques of RAG versus long-context models.
As context windows grow, the "just put it all in" option gets more viable more often, and
knowing where that line currently sits is genuinely useful judgment.

---

<div align="center">

**[← Chapter 14](../ch14-measuring-retrieval/)** · **[The Book](../../readme.md)** · **[Project C → Production RAG](../project-c-production-rag/)**

*Chapter 15 of 31 · Week 14 · End of Part III theory*

</div>
