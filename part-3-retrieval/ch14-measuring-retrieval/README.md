# Chapter 14 · Measuring Retrieval

### "How do you know your RAG system is actually good?"

> **Week 13 · ~22 hours · The most important chapter in Part III**
>
> Not the most interesting. The most important. Almost anyone can build retrieval. Very few
> people can tell you whether theirs works. Be one of those people.

---

## 14.0 · Why this chapter exists

Chapter 1 warned you about the Demo Trap. This is the chapter that gets you out of it.

Here is the question, and it comes up in essentially every interview for these roles:

> **"How do you know your RAG system is actually good?"**

The answer that ends the interview:

> *"I tried a bunch of questions and the answers looked right."*

The answer that gets you the offer:

> *"I have a gold set of 120 questions with labelled relevant chunks, split into train and
> test. Recall@10 on the test set is 0.87, up from 0.71 when I started. The biggest single
> gain was adding a reranker — that moved MRR from 0.52 to 0.79. I know my remaining failures
> are mostly multi-hop questions, because I categorise every failure, and I know that's the
> next thing to work on."*

Both candidates built the same system. One can be trusted with it.

And this isn't interview theatre. **Without measurement you cannot improve anything.** Every
change you make to a retrieval system is a guess, every guess feels like an improvement, and
you will confidently ship regressions. Chapters 11, 12 and 13 all ended by telling you to
measure something. This is where you learn how.

---

## 14.1 · Separate the two failures

A RAG system can fail in two entirely different places, and conflating them makes debugging
impossible.

```
   question ──▶ ┌────────────┐ ──▶ chunks ──▶ ┌────────────┐ ──▶ answer
                │ RETRIEVAL  │                │ GENERATION │
                └────────────┘                └────────────┘

    Failure 1: the right chunk         Failure 2: the right chunk
    was never retrieved                was retrieved, and the model
                                       still answered badly
```

These need different metrics, different fixes, and different chapters:

| | Retrieval failure | Generation failure |
|---|---|---|
| **Symptom** | Answer is wrong or "I don't know" | Answer contradicts the provided chunk |
| **Fix lives in** | Chunking, embeddings, search (Ch 11–13) | Prompting, model choice (Ch 7, 15) |
| **Measured by** | This chapter | Chapter 22 |

**Measure retrieval separately and first.** If the right chunk never reaches the model, no
prompt engineering will save you — and people spend weeks tuning prompts to fix what is
actually a chunking bug.

> **The diagnostic question: was the answer in the retrieved context?** If no, it's retrieval.
> If yes, it's generation. Answer that question before you change anything.

---

## 14.2 · The gold set

A gold set is a list of queries, each labelled with which chunks should be retrieved for it.

```python
@dataclass(frozen=True)
class GoldQuery:
    id: str
    query: str
    relevant_chunk_ids: set[str]            # binary relevance
    graded: dict[str, int] | None = None    # optional: 0–3 per chunk
    category: str | None = None             # "factual" | "multi-hop" | "identifier" | ...
    notes: str | None = None
    conversation: list[dict] | None = None  # for multi-turn queries
```

Building this is tedious, manual, and **it is the job.** There is no shortcut that produces a
trustworthy result, and the hours you spend here are what make every subsequent hour of tuning
meaningful.

### Where the queries come from

In descending order of value:

**1 · Real user queries.** If you have logs, use them. They contain the vocabulary, the typos,
the ambiguity and the shape of actual demand. Nothing you invent will match them.

**2 · Queries from the people who'll use it.** Ask ten domain experts for the ten questions they
most want answered. You get real questions and stakeholder buy-in at the same time.

**3 · Questions generated from your documents.** Fast, scalable, and biased — see section 14.7.
Fine as a supplement, dangerous as the only source.

**4 · Questions you invented.** Better than nothing. Beware: you will unconsciously write
questions your system already handles.

### How many

| Size | Use |
|---:|---|
| 20 | A smoke test. Enough to catch a catastrophe, not enough to compare configurations |
| **50–100** | **The practical minimum for real work** |
| 200–500 | Solid. Enough to slice by category and trust the slices |
| 1,000+ | Only if you have real logs to draw from |

Start with 50. Add every failure you find, forever — a gold set that grows with your production
failures is one of the most valuable assets a retrieval system has.

### Split it, immediately

```python
train, test = split(gold_set, ratio=0.7, seed=42)
```

**Tune on train. Report on test. Look at test as rarely as you can bear.**

Without this, you will overfit. You'll tune chunk size, `ef_search`, RRF weights and reranker
depth against the same 80 questions until your system is excellent at those 80 questions and
no better than baseline at anything else. This happens to everyone who skips the split, and
it's invisible from the inside — the numbers go up the whole time.

### Labelling: the honest process

For each query, find every chunk that should be retrieved. The workable method:

1. Run a **deliberately generous** retrieval — top 50, hybrid, no filters.
2. Read each candidate and mark it relevant or not.
3. Search manually for anything you suspect was missed.
4. Record graded relevance where it's meaningful:

```
3 = directly and completely answers the question
2 = contains part of the answer
1 = related, provides useful context
0 = not relevant
```

Time cost: roughly **2–5 minutes per query.** A hundred queries is a solid day's work.

> **That day is the highest-ROI day in Part III.** Everything after it is measurable, and
> nothing before it was. People skip it because it's boring, and then spend three weeks
> guessing.

**One warning about step 1:** labelling only what your current system retrieves builds your
system's blind spots into your gold set — the relevant chunks it never surfaces are never
labelled, so it scores perfectly on a test that excludes its failures. Always search manually
as well, and add relevant chunks you find later.

---

## 14.3 · The metrics

Five. You need to understand all five and will mostly report two.

Throughout: **k** is how many results you retrieve, **relevant** means labelled relevant in
your gold set.

### Hit Rate @k — "did we find anything useful?"

```
hit_rate@k = (queries with ≥1 relevant chunk in top k) / (total queries)
```

The simplest and the bluntest. For single-fact questions where one good chunk is enough, it's
often the metric that matches reality.

**Blind spot:** it doesn't care whether the relevant chunk was ranked 1st or 10th, and it
doesn't care if you missed four other relevant chunks.

### Recall @k — "what fraction of the good stuff did we get?"

```
recall@k = (relevant chunks in top k) / (all relevant chunks for this query)
```

**This is the headline metric for the retrieval stage**, because of the pipeline shape from
section 13.3: stage one's job is to not *miss* the answer. Ordering is stage two's problem.

```
Query has 4 relevant chunks. Top 10 contains 3 of them.
recall@10 = 0.75
```

**Blind spot:** retrieve everything and recall@k hits 1.0. Always report it at a fixed, sane k.

### Precision @k — "how much of what we returned was junk?"

```
precision@k = (relevant chunks in top k) / k
```

Matters because irrelevant chunks in the context are not free: they cost tokens, and from
section 5.11 they actively distract the model. **Precision is what you optimise after
reranking**, when you're choosing the final 3–5 chunks.

Recall and precision trade off. Retrieve 50 and recall rises, precision falls. That tension is
exactly why the two-stage pipeline exists.

### MRR — "how high was the first good result?"

```
MRR = mean over queries of  1 / (rank of the first relevant chunk)
```

```
first relevant at rank 1 → 1.00
                rank 2 → 0.50
                rank 3 → 0.33
                rank 10 → 0.10
            not found → 0.00
```

**MRR is your reranking metric.** It's sensitive to position in exactly the way hit rate isn't,
and when you add a reranker, MRR is where you'll see it.

### nDCG @k — "the whole ranking, properly graded"

The most complete metric, and the one most worth understanding rather than just computing.

Two ideas:

**Gain** — each result contributes according to its graded relevance (a 3 is worth more than a
1).
**Discount** — a result contributes less the further down it appears, on a logarithmic curve.

Sum those into DCG, then divide by the DCG of the *ideal* ranking to normalise into 0–1.

```python
import math

def dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))

def ndcg_at_k(retrieved_ids: list[str], graded: dict[str, int], k: int) -> float:
    actual = [graded.get(cid, 0) for cid in retrieved_ids[:k]]
    ideal = sorted(graded.values(), reverse=True)[:k]
    idcg = dcg(ideal)
    return dcg(actual) / idcg if idcg > 0 else 0.0
```

**Use nDCG when relevance is genuinely graded** — when "partially answers" is a real category in
your domain. Use the simpler metrics when relevance is binary.

### Which to report

| Question | Metric |
|---|---|
| Is the answer reaching the context at all? | **recall@k** (k = your retrieval width) |
| Is my reranker working? | **MRR**, **nDCG@5** |
| Am I wasting context on junk? | **precision@5** |
| Simple one-fact corpus? | **hit_rate@5** |

> **Report recall@k and MRR as your headline pair.** Recall answers "can we find it," MRR
> answers "do we rank it well." Together they cover both stages of the pipeline, and they're
> the two numbers an interviewer will understand immediately.

---

## 14.4 · Running an evaluation

```python
@dataclass
class EvalResult:
    config_name: str
    n_queries: int
    hit_rate_at_5: float
    recall_at_10: float
    precision_at_5: float
    mrr: float
    ndcg_at_5: float
    p50_latency_ms: float
    p95_latency_ms: float
    cost_per_query_usd: float
    per_query: list[QueryResult]      # keep this — section 14.5 needs it
    by_category: dict[str, float]     # and this
```

Three rules for the harness itself:

**1 · Report latency and cost alongside quality.** A configuration that raises recall by 0.02
and doubles latency is not obviously better. Present all three or you'll make bad tradeoffs.

**2 · Keep per-query results.** Aggregates tell you *that* something changed; per-query results
tell you *what*. You will spend far more time reading individual failures than reading
averages.

**3 · Slice by category.** An aggregate of 0.85 can hide recall of 0.95 on factual questions
and 0.40 on multi-hop ones. **The aggregate is almost never the interesting number.**

```
                    recall@10    n
  factual              0.94      52
  multi-hop            0.41      18    ← here is your actual problem
  identifier           0.88      15
  comparison           0.72      15
  ────────────────────────────────
  overall              0.81     100
```

That table tells you what to work on. The number 0.81 does not.

### Make it a command

```bash
uv run eval-retrieval --config baseline --split train
uv run eval-retrieval --compare baseline,hybrid,hybrid+rerank --split train
uv run eval-retrieval --config final --split test        # rarely
```

If running an evaluation takes more than one command, you won't do it often enough, and the
whole discipline collapses. Make it trivial.

---

## 14.5 · Reading the results

Aggregate numbers tell you where you are. **Failures tell you what to do.**

### The diagnostic tree

For every query where recall@10 is low, work down this list:

```
Was the relevant chunk retrieved at all (at any k)?
│
├─ NO → Is the information even in your corpus?
│        ├─ NO  → a corpus problem. Nothing in Part III can fix it.
│        │        Log it — it's a content gap, and that's a real finding.
│        └─ YES → Is it in one chunk, or split across two?
│                 ├─ SPLIT  → chunking problem (Ch 11)
│                 └─ INTACT → Does the chunk make sense in isolation?
│                             ├─ NO  → enrichment problem (11.8)
│                             └─ YES → a search problem:
│                                      · exact term?      → BM25 weight (13.1)
│                                      · negation?        → reranking (13.3)
│                                      · vague query?     → rewriting (13.4)
│                                      · asymmetric?      → HyDE (13.5)
│                                      · ANN missed it?   → ef_search (12.3)
│
└─ YES, but ranked low → a ranking problem → reranking (13.3)
```

Categorise every failure this way and you'll find that failures cluster. Usually three or four
causes account for most of them, and fixing the top cause moves the number more than a week of
general tuning.

### The failure log

```python
@dataclass
class Failure:
    query_id: str
    query: str
    category: str
    cause: str              # "chunk_split" | "not_in_corpus" | "ranking" | ...
    expected_chunks: list[str]
    retrieved_top_10: list[str]
    notes: str
```

**Keep this file forever.** It is your roadmap, your regression suite, and — when you write it
up — the most convincing thing in your portfolio.

---

## 14.6 · Hill climbing

The actual practice of improving a number, done in a way that doesn't fool you.

### The loop

```
1. Measure baseline on TRAIN. Record everything.
2. Read 10 failures. Categorise them.
3. Form a hypothesis: "most failures are X; change Y should fix them."
4. Change ONE thing.
5. Re-measure on TRAIN.
6. Did the target category improve? Did anything else regress?
7. Keep or revert. Record the result and the reasoning either way.
8. Repeat.
```

**One change at a time.** Change chunk size and add a reranker together, and you learn nothing
about either. It feels slower. It is dramatically faster, because you accumulate knowledge
instead of coincidences.

### A real progression

What this looks like over a couple of weeks:

| # | Change | recall@10 | MRR | p95 | Note |
|:---:|---|:---:|:---:|---:|---|
| 0 | Vector only, fixed 1000-char chunks | 0.61 | 0.44 | 40ms | baseline |
| 1 | Structural chunking, 600 tokens | 0.71 | 0.51 | 42ms | biggest chunking win |
| 2 | + metadata contextualisation | 0.76 | 0.55 | 42ms | cheap, free |
| 3 | + BM25, RRF | 0.83 | 0.58 | 65ms | identifiers fixed |
| 4 | + cross-encoder reranker | 0.83 | **0.79** | 310ms | recall flat, ranking transformed |
| 5 | + query rewriting (multi-turn) | 0.87 | 0.81 | 480ms | only helps follow-ups |
| 6 | + HyDE | 0.88 | 0.81 | 890ms | **not worth 400ms — reverted** |

Read row 4 carefully: **recall didn't move and MRR jumped 0.21.** That's exactly what a
reranker should do — it doesn't find new chunks, it orders the ones you have. If you were only
tracking recall, you'd have concluded the reranker did nothing and thrown away your biggest
win.

**That's why you report both metrics.**

And read row 6: a change that improved quality and was **reverted anyway**, because the latency
cost wasn't worth 0.01 recall. Being able to say that in an interview demonstrates judgment
rather than enthusiasm.

### Know when to stop

Diminishing returns arrive. Signs you're there:

- Changes move the number by less than the run-to-run noise.
- The remaining failures are mostly "not in corpus" — a content problem, not a retrieval one.
- You're tuning fourth-decimal constants.
- Latency is rising faster than quality.

**Stop and go to Chapter 15.** A recall of 0.87 with good generation beats 0.91 with bad
generation, and at some point the marginal hour is better spent elsewhere.

---

## 14.7 · The traps

### Overfitting to the gold set

The most common and the most insidious. Your train-set numbers climb beautifully; real
performance doesn't move.

**Defences:** the train/test split, touching test rarely, and adding fresh queries over time.
If train and test diverge significantly, you've overfit — believe the test set.

### Gold set rot

Your corpus changes. Documents are added, edited, deleted. Chunk IDs shift. Suddenly your gold
set references chunks that no longer exist and your numbers collapse for reasons that have
nothing to do with your retrieval.

**Defences:** label by *document plus text span* rather than by chunk ID where you can, pin your
gold set to a corpus version, and re-validate it whenever you re-index. Build this in early —
retrofitting it is painful.

### Synthetic questions that flatter you

Generating questions from your documents is fast and tempting:

```python
GEN_PROMPT = """Write 3 questions answerable using only this passage.
Make them sound like questions a real user would ask.
<passage>{chunk}</passage>"""
```

The bias: **the question is generated from the chunk, so it reuses the chunk's vocabulary.**
Retrieval finds it trivially. Your recall looks wonderful and means little, because real users
don't phrase questions in your documents' words — that's the entire problem retrieval exists to
solve.

**If you use synthetic questions:** explicitly instruct paraphrasing and vocabulary variation,
generate from *documents* rather than chunks, mix them with real questions, and treat synthetic
scores as an upper bound rather than an estimate.

### Measuring only the average

Covered in 14.4 and worth repeating because it's so easy to slip into. **Always slice.** The
average is where problems hide.

### Testing only single-turn

Your eval is 100 standalone questions. Production is conversations. Follow-up questions retrieve
terribly without rewriting (section 13.4), and your single-turn eval will never show it.

**Include conversational queries in your gold set.** That's what the `conversation` field is
for.

---

## 14.8 · Build it

**A retrieval evaluation harness.** This is the deliverable that makes Project C credible.

```
src/genai_toolkit/evaluation/
├── gold.py          GoldQuery, loading, validation, train/test split
├── metrics.py       hit_rate, recall, precision, mrr, ndcg
├── runner.py        run a config over a split, collect per-query results
├── compare.py       run N configs, produce the comparison table
├── diagnose.py      categorise failures by the section 14.5 tree
└── report.py        console tables, markdown, and a plot

eval/
├── gold/
│   ├── queries.yaml       your gold set — version controlled
│   └── CHANGELOG.md       what you added, when, why
├── results/               one JSON per run, timestamped
└── failures.md            the running failure log
```

Requirements:

1. **A gold set of at least 50 queries**, from real or expert-sourced questions, with labelled
   relevant chunks and categories. Include at least 10 conversational ones.
2. **A deterministic train/test split** by seed.
3. **All five metrics**, unit-tested against hand-computed examples. *(Metric bugs are silent
   and catastrophic — test them.)*
4. **Latency and cost** recorded per query.
5. **Per-category slicing** in every report.
6. **A comparison mode** producing the section 14.6 table for N configurations.
7. **Failure diagnosis** that categorises each failure by cause.
8. **Gold-set validation** — fail loudly if a referenced chunk no longer exists.
9. `make check` green.

### Then do the work

**Take your Chapter 13 pipeline through at least six measured configurations.** Produce your own
version of the section 14.6 table, with your numbers, on your corpus.

Then write, in `eval/FINDINGS.md`:

- The baseline and the final numbers
- What each change was worth
- What you tried and **reverted**, and why
- Your remaining failure categories, with counts
- What you'd do next, and what you'd expect it to be worth

That document is the single most valuable artefact you produce in Part III. It is the answer to
the interview question, written down.

---

## 14.9 · Exercises

**1 · Compute the metrics by hand.** Take one query with 4 relevant chunks and a retrieved list
of 10. Compute hit rate, recall, precision, MRR and nDCG on paper. Then check your code agrees.
**Do this before trusting your implementation** — metric bugs are silent.

**2 · Build the gold set.** 50 queries, properly labelled. Time yourself. Report the minutes per
query. *(This is the exercise. There's no way around it.)*

**3 · Prove the synthetic bias.** Generate 20 synthetic questions from chunks. Measure recall.
Then rewrite those same 20 questions in your own words without looking at the chunks. Measure
again. **Report the gap.**

**4 · Demonstrate overfitting.** Tune aggressively on train for ten iterations, checking test
each time but ignoring it. Plot both curves. Watch them diverge.

**5 · Metric disagreement.** Construct two retrieval configurations where recall@10 prefers A
and MRR prefers B. Explain which you'd ship and why.

**6 · k sensitivity.** Plot recall@k for k = 1, 3, 5, 10, 20, 50. Where does the curve flatten?
That's your answer for how wide to cast before reranking (section 13.6).

**7 · Inter-annotator agreement.** Have someone else label 20 of your queries independently.
Measure how often you agree. **If agreement is below ~80%, your relevance criteria are
ambiguous** and your gold set is noisier than you think.

**8 · Regression guard.** Add an eval run to CI that fails the build if recall@10 on the train
split drops more than 0.03. *(This is Chapter 22's central idea, arriving early — and it's what
makes prompt and config changes safe.)*

---

## 14.10 · Checkpoint

> **Move on to Chapter 15 when all of these are true.**

**Answer, out loud, in under 90 seconds:**

1. **"How do you know your RAG system is actually good?"** — with your real numbers.

**Explain:**

2. Why retrieval and generation failures must be measured separately, and how to tell them
   apart.
3. What each of the five metrics measures, and which question each answers.
4. Why recall is the headline for retrieval and MRR for reranking.
5. Why a reranker can leave recall unchanged while transforming MRR.
6. Why synthetic questions inflate your scores.
7. What a train/test split protects you from, and how you'd detect that it's happening.
8. Why the aggregate number is almost never the interesting one.

**Verify:**

9. A gold set of 50+ labelled queries, version controlled, including conversational ones.
10. All five metrics implemented and unit-tested against hand-computed values.
11. A comparison table of 6+ configurations with quality, latency and cost.
12. A categorised failure log with counts by cause.
13. `eval/FINDINGS.md` written, including something you reverted.
14. An eval running in CI that can fail the build.

Number 1 is the whole chapter. Practise saying it out loud until it's fluent, because you will
say it in an interview.

---

## 14.11 · Going deeper (optional)

**Read about TREC** and the history of information retrieval evaluation. Decades of careful
thought about exactly this problem. It's where these metrics come from and why they're shaped
as they are.

**Read the nDCG paper** if you want to understand the logarithmic discount properly. The
argument for *why* that particular curve is short and convincing.

**Look at RAG evaluation frameworks** (RAGAS and similar). Useful for ideas — especially their
generation-side metrics like faithfulness and answer relevance. Understand the metrics before
adopting a framework, though; a framework that computes numbers you can't interpret is worse
than no framework.

**If you want the honest frontier:** search for critiques of LLM-as-judge evaluation. You'll
use that technique in Chapter 22, and knowing its failure modes beforehand will make you use it
better.

---

<div align="center">

**[← Chapter 13](../ch13-search-that-works/)** · **[The Book](../../readme.md)** · **[Chapter 15 → RAG Architectures & Failure Modes](../ch15-rag-architectures/)**

*Chapter 14 of 31 · Week 13*

</div>
