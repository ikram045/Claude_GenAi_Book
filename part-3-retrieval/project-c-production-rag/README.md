# 🔨 Project C · Production RAG

### Week 15 · ~22 hours · The project that gets you interviews

---

## The brief

Build a **retrieval-augmented question answering system over a corpus you actually care
about** — and prove it works with numbers.

The building is the easy half. You've already built every component across Chapters 10–15.
This project is about assembling them, **measuring the result, improving a number, and writing
down what you learned.**

> **The deliverable is not the system. The deliverable is the system plus the evidence.**
>
> A GitHub repo containing a working RAG pipeline is worth very little — there are tens of
> thousands of them. A repo containing a working RAG pipeline, a gold set, an ablation table
> showing what each change was worth, a categorised failure log, and a findings document
> explaining what you'd do next is worth a great deal, because almost nobody has one.

This is the project you'll talk about in interviews. Choose the corpus accordingly.

---

## Choosing a corpus

This decision matters more than any technical choice you'll make this week.

### What makes a good corpus

**You care about it.** You'll spend 22 hours reading its chunks and labelling its queries. Pick
something you'll tolerate.

**You can judge relevance.** You must be able to look at a chunk and know whether it answers a
question. A corpus in a domain you don't understand makes your gold set worthless.

**It's genuinely messy.** Real PDFs, inconsistent formatting, multiple document versions. A
clean corpus makes the project easy and unconvincing.

**Between roughly 200 and 5,000 pages.** Smaller and RAG is the wrong tool (section 15.8).
Larger and ingestion eats your week.

**You can share it, or describe it.** An interviewer should be able to understand the domain in
thirty seconds.

### Good options

| Corpus | Why it works |
|---|---|
| **Flutter / Dart documentation + your own notes** | You know it deeply, judging relevance is instant, and it's a natural story: *"I built this to answer questions about the framework I spent three years in"* |
| **A large open-source project's docs + issues + code** | Messy, real, multi-format, and questions are genuinely hard |
| **Government or regulatory documents** for a domain you know | Terrible PDFs, versioned policies, conflicting text — every failure mode in Chapter 15 appears naturally |
| **A technical book or paper collection** in your field | Structured, long, and you can judge answers |
| **Your own work documents**, if you may use them | Most useful, hardest to share |

### One option to avoid

A tidy collection of clean Markdown files. It will work on the first try, teach you nothing,
and impress nobody.

> **Recommendation:** Flutter/Dart docs plus your own accumulated notes. You have unmatched
> domain judgment, it's genuinely messy, it's publicly shareable, and the career narrative
> writes itself.

---

## Requirements

### The system

**Ingestion**
- Multiple formats (at minimum: Markdown, HTML, PDF)
- Structural chunking with heading paths
- Complete metadata, including versions and dates
- Contextual enrichment
- Deduplication and near-duplicate detection
- Incremental re-indexing that skips unchanged documents
- Resumable, with progress reporting

**Retrieval**
- Hybrid: vector + BM25, fused with RRF
- Cross-encoder reranking
- Conversational query rewriting
- Metadata filtering
- Configurable and instrumented at every stage

**Generation**
- Grounded answering with mandatory citations
- Citation verification (index validity at minimum)
- `INSUFFICIENT_CONTEXT` handling with gap logging
- Conflict detection between sources
- Streaming responses

**Serving**
- FastAPI, SSE streaming (Chapter 4)
- A trace per request, retrievable by request ID
- Cost and latency tracking (Chapter 9)
- Docker, CI

### The evidence — this is what the project is for

- [ ] **A gold set of 100+ queries**, version controlled, with labelled relevant chunks,
      categories, and at least 15 conversational follow-ups
- [ ] **A train/test split**, with test used sparingly
- [ ] **An ablation table** of at least 8 configurations, reporting recall@10, MRR, p95 latency
      and cost per query
- [ ] **A categorised failure log**, mapped to Chapter 15's eight modes with counts
- [ ] **A content-gap report** derived from `INSUFFICIENT_CONTEXT` responses
- [ ] **`FINDINGS.md`** — the narrative: baseline, what you changed, what each was worth, what
      you reverted and why, what's left

### Quality bar

| Requirement | Verified by |
|---|---|
| `mypy --strict` clean | `make type` |
| ruff clean | `make lint` |
| Coverage ≥ 80%, meaningful | `make test` |
| **Eval runs in CI and can fail the build** | GitHub Actions |
| Offset fidelity property test passes | `make test` |
| No orphaned chunks | CI check |
| `docker compose up` works from a clean clone | Try it |
| Final prompt logged on every request | Read a trace |

---

## The week, day by day

Twenty-two hours goes fast. A realistic allocation:

| | Hours | Work |
|---|:---:|---|
| **Mon** | 3 | Corpus selection and ingestion. Get documents in, read 50 chunks, fix the worst extraction problems |
| **Tue** | 3 | Index, wire up the baseline pipeline (vector only). **Measure it.** This is your baseline row |
| **Wed** | 3 | Build the gold set. Budget the whole session for it — this is the highest-value work of the week |
| **Thu** | 3 | Ablations: hybrid, RRF, reranking. One change at a time, measure each |
| **Fri** | 2 | Generation: citations, verification, refusal, conflicts |
| **Sat** | 5 | Serving, Docker, CI, failure analysis, fix the top failure category |
| **Sun** | 3 | `FINDINGS.md`, README, and a demo recording |

> **If you're running short, cut features — never the measurement.** A system with hybrid
> retrieval, a gold set and an ablation table beats a system with every technique in Part III
> and no numbers. The measurement *is* the project.

---

## `FINDINGS.md` — the most important file

This is what an interviewer will read. Give it the structure of an engineering report.

```markdown
# Findings — Flutter Documentation RAG

## The corpus
1,847 documents · 23,410 chunks · Markdown, HTML, 40 PDFs
Known issues: 12 documents are scanned PDFs with no text layer (excluded);
3 API pages exist in both v3 and v4 versions (both indexed, version filtered).

## The gold set
127 queries · 89 train / 38 test
Sources: 60 from my own search history, 40 from Stack Overflow questions
tagged `flutter`, 27 written by me to cover gaps.
Categories: factual (58), how-to (31), identifier (18), comparison (12),
multi-hop (8). 19 are conversational follow-ups.
Labelling took 6.5 hours — roughly 3 minutes per query.

## Results

| # | Configuration              | recall@10 | MRR  | p95    | $/query |
|---|----------------------------|----------:|-----:|-------:|--------:|
| 0 | Vector, fixed 1000-char    |      0.58 | 0.41 |   38ms | 0.0021  |
| 1 | + structural chunking      |      0.69 | 0.48 |   40ms | 0.0021  |
| 2 | + contextual enrichment    |      0.74 | 0.52 |   40ms | 0.0023  |
| 3 | + BM25 & RRF               |      0.84 | 0.57 |   71ms | 0.0023  |
| 4 | + reranking                |      0.84 | 0.78 |  340ms | 0.0026  |
| 5 | + query rewriting          |      0.88 | 0.80 |  510ms | 0.0031  |
| 6 | + HyDE                     |      0.89 | 0.80 |  940ms | 0.0044  |
| 7 | **Final (5, no HyDE)**     |  **0.88** | 0.80 |  510ms | 0.0031  |

**Test set (checked twice): recall@10 = 0.86, MRR = 0.78.**

## What each change was worth

**Structural chunking (+0.11 recall).** The single biggest ingestion win. Fixed-size
chunking was splitting code examples from their explanations — 14 of my first 20
failures were exactly this.

**Contextual enrichment (+0.05).** Metadata-based only; I measured LLM-based
enrichment as +0.02 more for 8x the indexing cost and skipped it.

**BM25 + RRF (+0.10).** Almost entirely on the identifier category, which went
from 0.51 to 0.94. Widget class names are rare tokens; BM25 finds them exactly.

**Reranking (+0.00 recall, +0.21 MRR).** Recall didn't move because the chunks
were already being retrieved — they were ranked 8th-20th. Reranking moved them
into the top 3, which is what actually reaches the model. **This was the single
largest quality improvement in the project**, and tracking only recall would have
made it look worthless.

**Query rewriting (+0.04 overall, +0.31 on conversational).** Only affects
follow-up questions, which are 15% of the gold set. The category-level number is
the real story.

## What I reverted

**HyDE.** +0.01 recall for +430ms p95 and 42% higher cost per query. Not worth
it on this corpus — the questions are already fairly document-shaped because
they come from developers who read the docs.

**LLM-based contextual enrichment.** +0.02 for 8x index cost. Would reconsider
for a corpus where chunks reference outside context more heavily.

## Remaining failures (n=21 on train)

| Mode | Count | Notes |
|---|---:|---|
| 1 · Missing content | 8 | Genuinely not in the docs — see content gaps |
| 7 · Incomplete (multi-hop) | 6 | "How does X differ from Y" needs two searches |
| 5 · Not extracted | 4 | Answer present, model didn't connect it |
| 8 · Stale/conflicting | 3 | v3 vs v4 API pages |

## What I'd do next

1. **Agentic retrieval for multi-hop** — 6 failures, and section 15.4 says this
   is what it's for. Estimated +0.03 recall, ~800ms cost. Worth prototyping.
2. **Version-aware routing** — detect when a query implies a Flutter version and
   filter. Would close most of the 3 stale failures cheaply.
3. **Not** more retrieval tuning. 8 of 21 remaining failures are content gaps,
   which no retrieval work can fix.
```

Read that back. **Every paragraph demonstrates something an interviewer wants to see:** you
measured before optimising, you attributed gains to specific changes, you understood *why*
reranking helped, you rejected a technique on cost grounds, you categorised what's left, and
you know when to stop tuning.

That's the project.

---

## Stretch goals

Only after the evidence is complete:

1. **Agentic retrieval** for the multi-hop category. A preview of Part IV, motivated by your own
   failure log.
2. **A version-aware router** — the natural fix for failure mode 8 on a versioned corpus.
3. **An evaluation dashboard** — a small web page showing your ablation table, failure
   distribution and content gaps. Makes the work legible in ten seconds.
4. **Incremental corpus updates** — watch a folder, re-index changed documents only, report the
   delta.
5. **A Flutter client.** Mobile app over your own SSE endpoint, with citation links. **Your
   differentiator, on your flagship project.** If you do one stretch goal, do this one.

---

## How to present it

### README, in this order

1. **What it does** — two sentences, plus the corpus in one line
2. **The headline number** — *"recall@10 of 0.86 on a held-out test set of 38 queries, up from
   0.58 at baseline."* Put it near the top. It's the thing that makes a reader keep reading.
3. **A demo** — asciinema or a short video. Streaming, with citations.
4. **Quickstart** — clone to answering questions in five minutes
5. **Architecture** — one diagram, the pipeline from Chapter 13
6. **[FINDINGS.md](FINDINGS.md)** — linked prominently
7. **Design decisions** — with the rejected alternatives
8. **What I'd do differently**

### The interview questions

You will be asked these. Rehearse them out loud.

> **"How do you know it's good?"**
> The gold set, the split, the headline numbers, and the honest statement that 8 of your
> remaining failures are content gaps rather than retrieval problems.

> **"What was the biggest improvement?"**
> Reranking — and the fact that it didn't move recall at all. Explaining *why* that's expected
> demonstrates you understand the two-stage architecture rather than having copied it.

> **"What didn't work?"**
> HyDE. Have the latency and cost numbers ready. Rejecting a popular technique with evidence is
> a stronger signal than adopting one.

> **"How would you scale this to 10 million chunks?"**
> Chapter 12: quantization before sharding, filtered search behaviour, index build time, the
> memory arithmetic. Know your current numbers so the extrapolation is grounded.

> **"What would you do next, and why?"**
> Your ranked list, with estimated impact from your failure distribution. This answer separates
> people who finished a project from people who own a system.

---

## Before you start

**Build the gold set on Wednesday, not on Sunday.** Everything after it is measurable and
everything before it is guesswork. People leave it to the end, run out of time, and produce
another unmeasured demo.

**Start with the baseline and measure it.** You cannot report an improvement without a starting
number, and you cannot reconstruct the baseline once you've changed five things.

**Read your chunks.** Fifty of them, by hand, on Monday. It's the cheapest quality work
available and almost nobody does it.

**One change at a time.** Every row in your ablation table must be one change from the row
above. Otherwise the table is a list of coincidences.

**Timebox to 22 hours.** If you're at hour thirty, stop, write `FINDINGS.md` with what you have,
and move to Chapter 16. An honest table with six rows beats an unfinished system with twelve.

---

<div align="center">

**[← Chapter 15](../ch15-rag-architectures/)** · **[The Book](../../readme.md)** · **[Chapter 16 → Tool Use](../../part-4-agents/ch16-tool-use/)**

*End of Part III · Week 15 of 34 · Nearly halfway*

</div>
