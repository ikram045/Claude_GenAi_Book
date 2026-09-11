# Chapter 13 · Search That Actually Works

### Hybrid retrieval, rank fusion, reranking, and query understanding

> **Week 12 · ~22 hours · Heavy code**
>
> Chapter 10 showed you what embeddings can't do. This chapter is the engineering answer to
> every one of those failures. It's also the chapter that takes a mediocre RAG system and
> makes it good.

---

## 13.0 · Why this chapter exists

Here is the entire argument, in one table. These are the failures from section 10.5, with the
fix for each:

| Embeddings can't handle | The fix | Section |
|---|---|---|
| Exact identifiers (`E4471`) | Keyword search | 13.1 |
| Rare domain terms | Keyword search | 13.1 |
| Negation ("not safe") | Reranking | 13.4 |
| Ranking quality generally | Reranking | 13.4 |
| Vague or conversational queries | Query rewriting | 13.6 |
| Asymmetric question/passage gap | HyDE | 13.7 |
| Multi-part questions | Query decomposition | 13.6 |

Pure vector search — the thing every tutorial teaches — handles none of these. And the fixes
are not exotic research: they're four well-understood techniques you can implement in a week.

> **The gap between "I built a RAG demo" and "I built a retrieval system" is almost entirely
> this chapter.**

---

## 13.1 · Keyword search, properly

Before neural retrieval there was lexical retrieval, and it is still excellent at things
embeddings are bad at. Don't treat it as legacy.

### BM25

The standard ranking function for keyword search. It scores a document for a query by asking
three questions:

1. **Does the document contain the query terms?** More occurrences, higher score.
2. **How rare is each term?** A document matching "Blorptastic" tells you far more than one
   matching "the". Rare terms are weighted heavily — this is **inverse document frequency**,
   and it's the heart of why BM25 works.
3. **How long is the document?** A term appearing twice in a short document is a stronger
   signal than twice in a long one. BM25 normalises for length.

It also applies **saturation**: the tenth occurrence of a term adds much less than the second.
That's what stops keyword-stuffed documents from dominating.

You don't need to implement it. Postgres has full-text search built in; every search engine and
most vector databases include BM25 or a close relative.

```sql
-- Postgres full-text search, using the tsv column from Chapter 12
SELECT id, display_text,
       ts_rank_cd(tsv, websearch_to_tsquery('english', %(query)s)) AS score
FROM chunks
WHERE tsv @@ websearch_to_tsquery('english', %(query)s)
ORDER BY score DESC
LIMIT 50;
```

### Where keyword search wins outright

```
Query: "error code E4471"
  Vector: returns chunks about errors in general. E4471 and E4472 are
          indistinguishable.
  BM25:   E4471 is a rare token. Exact match. Ranked first. Done.

Query: "Blorptastic Widget installation"
  Vector: "Blorptastic" was never in training; the vector is arbitrary.
  BM25:   maximally rare term, maximally weighted. Perfect.

Query: "section 14.2(b)"
  Vector: numbers are nearly invisible.
  BM25:   exact match.
```

Identifiers, part numbers, error codes, legal citations, version strings, people's names,
internal jargon. **Any query where the user knows the exact word they want.**

### Where it fails

```
Query: "how do I cancel my subscription"
Document: "Ending your membership: to close your account, navigate to..."

  BM25:   zero shared terms. No match. Nothing.
  Vector: strong match.
```

Exactly complementary. Which is the whole point.

---

## 13.2 · Hybrid search

Run both. Combine the results.

```
                  query
                ╱       ╲
      ┌────────╱─┐     ┌─╲────────┐
      │  VECTOR  │     │   BM25   │
      │  top 50  │     │  top 50  │
      └────┬─────┘     └─────┬────┘
           └────────┬────────┘
              ┌─────▼─────┐
              │  FUSION   │
              └─────┬─────┘
                 top 50
```

The immediate problem: **the two score scales are not comparable.**

```
Vector similarity:  0.0 – 1.0,  bunched between 0.6 and 0.9 (section 10.4)
BM25:               0 – unbounded, depends on corpus and query length
```

You cannot add them. You cannot average them. Normalising them (min-max, z-score) is possible
but fragile — a single outlier reshapes the whole distribution, and the "right" weighting
changes per query.

### Reciprocal Rank Fusion

The standard solution, and it's beautiful because it throws the scores away entirely and uses
only the **ranks**.

```
RRF_score(d) = Σ  1 / (k + rank_r(d))
              r
```

where `r` ranges over your retrievers, `rank_r(d)` is d's position in retriever r's list
(1-based), and `k` is a constant, conventionally 60.

```python
def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Fuse ranked lists of document ids. Scores are ignored; only order matters."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
```

Why it works so well:

- **Scale-free.** No normalisation, no tuning per retriever, no outlier sensitivity.
- **Agreement is rewarded.** A document ranked well by both retrievers accumulates from both
  and rises above either list's top result. That's usually exactly right.
- **`k` damps the top.** With `k=60`, rank 1 scores 1/61 and rank 2 scores 1/62 — close. This
  stops one retriever's confident-but-wrong first result from dominating. Lower `k` sharpens
  the preference for top ranks; higher `k` flattens it.
- **It extends trivially.** Three retrievers, five retrievers — same function.

### Weighting

When one retriever is systematically better for your corpus:

```python
scores[doc_id] += weight_r * (1.0 / (k + rank))
```

**Measure before you weight.** The intuition that "vectors are better" is often wrong on
technical corpora full of identifiers. Chapter 14 gives you the means to find out.

---

## 13.3 · Reranking

**The single highest-impact technique in this chapter.** If you do one thing from Part III
beyond hybrid search, do this.

### Why a second stage exists at all

Your retrievers used **bi-encoders**: the query and the document were embedded *separately*, and
compared by a cheap vector operation.

```
   BI-ENCODER (retrieval)             CROSS-ENCODER (reranking)

   query ──▶ [model] ──▶ vec ╲        query ─┐
                              ├─ cos          ├─▶ [model] ──▶ relevance score
   doc   ──▶ [model] ──▶ vec ╱        doc   ─┘

   Documents embedded once, offline.  Both read TOGETHER, at query time.
   Millions of comparisons, instant.  One model call PER DOCUMENT. Slow.
   Good.                              Much better.
```

A cross-encoder reads the query and the document **together**, with full attention between
them. It can see that the query asks about safety *during pregnancy* and this document says
*not* safe. It can weigh which parts of the document actually address the question.

It is also far too slow to run over a million documents. So:

### Cast wide, rerank narrow

```
   1M chunks
       │  hybrid retrieval (fast, approximate)
       ▼
     50 candidates            ← optimise for RECALL: is the answer in here at all?
       │  cross-encoder rerank (slow, accurate)
       ▼
      5 chunks                ← optimise for PRECISION: are these the best 5?
       │
       ▼
    language model
```

**This two-stage shape is the standard architecture of modern retrieval**, and each stage has a
different job. Stage one must not *miss* the answer; ordering barely matters. Stage two must
order correctly; it only sees what stage one passed through.

That framing tells you how to debug: if the answer wasn't in the 50, reranking cannot save you —
fix retrieval. If it was in the 50 but not the 5, fix reranking.

### What it costs and what it's worth

```
Hybrid retrieval:    ~20 ms
Rerank 50 candidates: ~150–400 ms
```

A few hundred milliseconds on a request that will spend seconds in the language model anyway.
And the quality improvement is typically large — often the biggest single jump you'll measure
in Part III.

**It also saves money.** Better ranking means you can send 3 chunks instead of 10, which cuts
input tokens substantially (section 9.5). A reranker frequently pays for itself.

### Options

| Approach | Notes |
|---|---|
| **Hosted reranking API** | Easiest, good quality, per-call cost |
| **Open cross-encoder** (`sentence-transformers` and similar) | Free, runs locally, needs a GPU for speed |
| **LLM-as-reranker** | Ask the model to score relevance. Flexible, expensive, slow. Good for low volume or unusual criteria |

Start with a hosted reranker or a small open cross-encoder. Measure the delta. It's usually the
easiest win available.

---

## 13.4 · Query understanding

Everything so far assumed the user's query is a good search query. It usually isn't.

### The conversational problem

```
User: "What's the refund window for enterprise customers?"
Bot:  "Enterprise customers have 30 days."
User: "What about standard?"
```

Embedding *"What about standard?"* retrieves nothing useful. The query is meaningless without
the conversation.

**Rewrite it into a standalone query before searching:**

```python
REWRITE_PROMPT = """Given the conversation, rewrite the final user message as a
standalone search query that makes sense without the conversation.

<conversation>
{history}
</conversation>

<final_message>
{message}
</final_message>

Output only the rewritten query, nothing else."""

# "What about standard?" → "refund window for standard customers"
```

> **This is mandatory for any multi-turn RAG system.** Without it, every follow-up question
> retrieves badly, and the failure is invisible in single-turn testing — which is exactly how
> it reaches production.

### Decomposition

```
"How does our refund policy compare to our warranty policy for enterprise?"
```

One query, two distinct information needs. A single search splits the difference and retrieves
mediocre results for both.

```python
# Decompose → search each → merge
["enterprise refund policy", "enterprise warranty policy"]
```

Search each independently, fuse the results with RRF. Better coverage of both halves. Don't
decompose everything — detect multi-part questions and handle those.

### Expansion

Generate paraphrases and search with all of them:

```
"cancel subscription"
  → "cancel subscription"
  → "end membership"
  → "close account"
  → "stop auto-renewal"
```

Fuse with RRF. Increases recall at the cost of latency and complexity. Worth measuring; not
always worth shipping.

### Domain glossaries

Cheap, deterministic, and effective where a general model doesn't know your vocabulary:

```python
GLOSSARY = {
    "BW":      "Blorptastic Widget",
    "P0":      "P0 critical priority incident",
    "the gw":  "Acme Gateway",
}
```

Expand known terms before embedding. No model call, no latency, and it fixes the rare-term
failure from section 10.5 directly.

---

## 13.5 · HyDE

The elegant fix for the asymmetry problem from section 10.6.

**The problem:** a question and its answer don't look alike, so their vectors aren't as close as
they should be.

**The insight:** so don't search with the question. Search with a *hypothetical answer*.

```python
HYDE_PROMPT = """Write a short passage that would answer this question, as it
might appear in documentation. It does not need to be factually correct — it
needs to look like the kind of passage that would contain the answer.

Question: {question}

Passage:"""
```

```
Question: "how do I reset my password"

Hypothetical answer:
"To reset your password, navigate to the account settings page and select
 the security options. Click 'Reset Password' and a confirmation link will
 be sent to your registered email address..."

  → embed THAT, and search with it
```

The hypothetical passage looks like a real passage. Passage-to-passage similarity is symmetric,
and it works much better.

**It does not matter that the hypothetical answer may be wrong.** You never show it to anyone.
You're using it purely as a better-shaped search key. That's a genuinely clever piece of
engineering, and it surprises people every time.

**The costs:** one extra language model call per query — latency and money. And for queries
where the model has no idea what the answer would look like, the hypothetical can steer you
wrong.

**When to use it:** queries that are short, questiony, and retrieving poorly. Measure it; it
helps substantially on some corpora and not at all on others.

---

## 13.6 · The full pipeline

Everything assembled:

```
                         user query + conversation
                                    │
                        ┌───────────▼───────────┐
                        │  QUERY UNDERSTANDING  │
                        │  rewrite · decompose  │
                        │  expand · glossary    │
                        └───────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼────┐   ┌──────▼─────┐  ┌──────▼─────┐
              │  VECTOR  │   │    BM25    │  │    HyDE    │
              │  top 50  │   │   top 50   │  │   top 50   │
              └─────┬────┘   └──────┬─────┘  └──────┬─────┘
                    └───────────────┼───────────────┘
                              ┌─────▼─────┐
                              │    RRF    │
                              │  top 50   │
                              └─────┬─────┘
                              ┌─────▼─────┐
                              │  RERANK   │  cross-encoder
                              └─────┬─────┘
                              ┌─────▼─────┐
                              │  top 3–5  │
                              └─────┬─────┘
                                    ▼
                             language model
```

### Build it incrementally, measuring each step

**Do not build this all at once.** Build it in this order, measuring after each addition, so you
know what each stage is worth on *your* data:

1. Vector only — the baseline
2. **+ BM25 and RRF** — usually a solid gain
3. **+ Reranking** — usually the biggest gain
4. **+ Query rewriting** — essential if multi-turn
5. **+ HyDE / decomposition / expansion** — measure; ship only what helps

You need Chapter 14 to do this properly. That's the order the book is in for a reason: build
the measurement, then tune.

> **Every stage adds latency, cost and a failure mode.** A pipeline with five stages has five
> places to break and five things to debug. Add a stage only when you have measured that it
> earns its place. This is the most common over-engineering trap in retrieval.

---

## 13.7 · Build it

Extend your Chapter 12 store into a real retrieval pipeline.

```
src/genai_toolkit/retrieval/
├── base.py            Retriever Protocol
├── vector.py
├── keyword.py         BM25 / Postgres FTS
├── hyde.py
├── fusion.py          RRF, weighted RRF
├── rerank.py          cross-encoder, behind a Protocol
├── query/
│   ├── rewrite.py     conversational → standalone
│   ├── decompose.py
│   ├── expand.py
│   └── glossary.py
└── pipeline.py        composable, configurable, instrumented
```

Requirements:

1. **Three retrievers** behind one Protocol: vector, keyword, HyDE.
2. **RRF fusion**, with optional per-retriever weights.
3. **Reranking** behind a Protocol, with at least one implementation and a pass-through
   no-op for comparison.
4. **Query rewriting** using conversation history. Mandatory.
5. **A configurable pipeline** — every stage switchable, so you can measure ablations.
6. **Instrumentation per stage**: latency, candidate count, and which retriever contributed
   each final result. **This last one is essential for debugging.**
7. **Graceful degradation** — if the reranker times out, return the fused results rather than
   failing the request.
8. `make check` green.

```python
@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float
    rank: int
    sources: list[str]        # ["vector:3", "bm25:1"] ← which retrievers found it
    rerank_score: float | None
```

That `sources` field is the most useful debugging field in your whole system. When a bad result
appears, you immediately know which retriever to blame.

### The experiments

**1 · Prove complementarity.** Take 30 queries. Run vector-only and BM25-only. For each query,
record whether the right answer was found by vector, by BM25, by both, or by neither. **Build
the 2×2 table.** The "only BM25" cell is your argument for hybrid search, in your own data.

**2 · Measure the reranker.** Same queries, hybrid retrieval, with and without reranking.
Measure how often the best chunk lands in the top 3. This is usually the largest single number
in your whole tuning effort.

**3 · Tune `k` in RRF.** Try 10, 30, 60, 100. Observe how it changes the balance between "one
retriever is very confident" and "both retrievers agree."

**4 · Query rewriting, on multi-turn.** Build 20 conversational follow-up questions. Measure
retrieval quality with and without rewriting. The gap will be large enough to settle the
question permanently.

**5 · HyDE, honestly.** Measure it on your corpus. Report whether it helped, by how much, and
what it cost in latency. **Be prepared for the answer to be "not worth it"** — that's a valid
and valuable finding.

**6 · Find the cast-wide knee.** Retrieve 10, 25, 50, 100, 200 candidates before reranking.
Measure final quality and total latency. Where does more recall stop helping?

**7 · Ablate everything.** Build the table: each configuration, its quality score, its p95
latency, its cost per query. **This table is a portfolio artefact** and the core of your
Project C write-up.

---

## 13.8 · Exercises

**1 · Implement BM25 from scratch.** On 1,000 documents. Compare your rankings to Postgres FTS.
You'll understand IDF and saturation properly, permanently.

**2 · Where RRF beats normalisation.** Implement min-max normalisation and weighted-sum fusion
as an alternative. Construct a case where an outlier score wrecks the normalised version and
RRF is unaffected.

**3 · An identifier test set.** Build 20 queries containing error codes, part numbers or
version strings. Measure vector-only, BM25-only, and hybrid. **This is section 10.5's failure,
fixed and quantified.**

**4 · A negation test set.** Build 15 query/document pairs where polarity is the only
difference. Measure how often vector retrieval ranks the wrong-polarity document first, and how
often reranking corrects it.

**5 · LLM-as-reranker.** Implement one: ask the model to score 20 candidates for relevance.
Compare quality, latency and cost against a cross-encoder. When would you use each?

**6 · Rewriting failure modes.** Find three conversations where your rewriter produces a *worse*
query than the original. Diagnose why. Fix the prompt. *(Hint: it often over-specifies from
context that has moved on.)*

**7 · Latency budget.** Instrument every stage. Produce a waterfall for a single query showing
where the milliseconds go. Then cut total retrieval latency by 30% and say which stage you cut.

**8 · Adaptive pipelines.** Route short identifier-looking queries straight to BM25 and skip the
expensive stages. Measure the latency saving and confirm quality holds on those queries.

---

## 13.9 · Checkpoint

> **Move on to Chapter 14 when all of these are true.**

**Explain, out loud:**

1. What BM25 scores, and why IDF makes it good at rare terms.
2. Why vector and keyword search are complementary rather than competing.
3. Why you cannot simply add or average their scores.
4. How RRF works and why discarding the scores is a feature.
5. The difference between a bi-encoder and a cross-encoder, and why one can be used at scale.
6. Why "cast wide, rerank narrow" has different objectives at each stage.
7. Why query rewriting is mandatory for multi-turn RAG, and why its absence is invisible in
   testing.
8. Why HyDE works despite the hypothetical answer often being wrong.

**Write from memory:**

9. Reciprocal rank fusion.
10. A two-stage retrieve-then-rerank pipeline.
11. A conversational query-rewriting prompt.
12. A `RetrievalResult` that records which retrievers contributed.

**Verify:**

13. You have the complementarity 2×2 table from your own data.
14. You have measured the reranker's contribution as a number.
15. You have an ablation table covering every pipeline configuration, with quality, latency and
    cost.
16. Your pipeline degrades gracefully when the reranker fails.

Number 15 is the deliverable. It's the evidence that you tuned a system rather than assembled
one.

---

## 13.10 · Going deeper (optional)

**Read the RRF paper.** Two pages, one formula, and a surprising amount of empirical strength.
A good example of a simple idea that beats complicated ones.

**Read about cross-encoders versus bi-encoders** in the sentence-transformers documentation. The
architectural explanation for why one is accurate and the other is scalable is clearly written
and will stick.

**If you want the frontier:** look into late-interaction models (ColBERT and successors), which
sit between bi-encoders and cross-encoders — a vector per token, with cheap late matching.
They're increasingly practical and they attack exactly the precision problems in section 10.5.

**If you want the long view:** read about learning-to-rank. Modern neural retrieval is a
continuation of decades of information retrieval research, and knowing the lineage makes the
current techniques feel inevitable rather than arbitrary.

---

<div align="center">

**[← Chapter 12](../ch12-vector-databases/)** · **[The Book](../../readme.md)** · **[Chapter 14 → Measuring Retrieval](../ch14-measuring-retrieval/)**

*Chapter 13 of 31 · Week 12*

</div>
