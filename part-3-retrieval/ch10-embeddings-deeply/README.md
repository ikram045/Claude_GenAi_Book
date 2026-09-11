# Chapter 10 · Embeddings, Deeply

### Meaning as geometry — and the four things embeddings are quietly terrible at

> **Week 10 · ~22 hours · Concepts plus code**
>
> Part III begins. Retrieval is the most in-demand specific skill in AI application
> engineering, and this chapter is its foundation. Everything in Chapters 11–15 assumes you
> understand what a vector actually represents.

---

## 10.0 · Why this chapter exists

Most people learn embeddings like this: *"Text becomes a vector. Similar text has similar
vectors. Use cosine similarity."* Three sentences, and then straight to building a RAG demo.

The demo works. Then it's pointed at real documents and starts returning confidently
irrelevant results, and the person who learned those three sentences has no idea why, because
they never learned what "similar" actually means to an embedding model.

Here is a preview of what you'll be able to explain by the end of this chapter — a genuine
failure that has shipped in production systems more than once:

```
Query:     "Is this medication safe during pregnancy?"

Document A: "This medication is safe during pregnancy."
Document B: "This medication is NOT safe during pregnancy."
```

To an embedding model, **A and B are nearly identical.** Their cosine similarity is typically
above 0.95. The word "not" barely moves the vector, because these two sentences are about the
same topic, in the same register, using the same vocabulary — and topic similarity is what
embeddings measure.

A naive vector search will happily return the one that kills someone.

That's not a reason to avoid embeddings. It's a reason to understand precisely what they
measure, so you can build systems that compensate — which is what Chapters 13, 14 and 15 do.

---

## 10.1 · Meaning as geometry

Section 5.3 introduced the idea. Let's make it solid.

An **embedding** is a fixed-length list of numbers representing a piece of text, produced so
that texts with similar meanings land near each other in that space.

```
"a small domestic cat"   →  [ 0.021, -0.334,  0.887, ..., 0.112]   (e.g. 1024 numbers)
"a kitten"               →  [ 0.019, -0.341,  0.879, ..., 0.108]   ← very close
"quarterly tax filing"   →  [-0.442,  0.118, -0.203, ..., 0.665]   ← far away
```

The number of dimensions varies by model — commonly 384, 768, 1024, 1536 or 3072. Each
dimension is a learned axis. Almost none of them correspond to anything a human could name;
the *geometry as a whole* carries the meaning, not any individual coordinate.

### Why this is such a powerful idea

Keyword search asks: *does this document contain these words?*
Vector search asks: *is this document about the same thing?*

```
Query: "how do I cancel my subscription"

Keyword search finds:  documents containing "cancel" AND "subscription"
Vector search finds:   "Ending your membership", "Turning off auto-renewal",
                       "Closing your account"
```

None of those three share a keyword with the query. All three are the right answer.

This is the whole promise: **searching by meaning rather than by string.** It's genuinely
transformative, and it's also why people over-trust it — because when it works, it feels like
comprehension.

---

## 10.2 · What an embedding model is

It is *not* a language model, and confusing the two causes real mistakes.

| | Language model | Embedding model |
|---|---|---|
| Input | Text | Text |
| Output | More text, token by token | One fixed-length vector |
| Size | Very large | Much smaller |
| Cost | Cents per request | Fractions of a cent per thousand |
| Speed | Hundreds of ms to seconds | Milliseconds |
| Purpose | Generate | Compare |

Architecturally they're related — an embedding model is usually a transformer too — but the
training objective is completely different. An embedding model is trained on **pairs**: this
question and this answer belong together; this question and that random passage do not. Over
millions of such pairs it learns to place related texts near each other.

That training objective is the single most important fact about embeddings, and section 10.5
is entirely about its consequences. **The model learned what "related" means from its training
pairs.** If your notion of related differs from theirs, the geometry will not serve you.

### Where you get them

Embeddings come from a different place than your language model. Three options:

| Option | Good for | Watch out for |
|---|---|---|
| **Hosted embedding API** | Getting started, quality, no infrastructure | Per-token cost, network latency, vendor lock-in of your index |
| **Open model, self-hosted** (`sentence-transformers` and friends) | Volume, privacy, offline, zero marginal cost | GPU or slow CPU, you own the ops |
| **Fine-tuned on your domain** | Specialised vocabulary where generic models fail | Needs training data and measurement — Chapter 27 |

Start with a good hosted model or a well-regarded open one. Optimise later, with evidence.

> **The lock-in you should know about before you index anything:** vectors from different
> models are **not comparable**. Switching embedding models means re-embedding your entire
> corpus. On a million documents that's real time and real money. Choose deliberately, and
> build your pipeline so re-embedding is a command you can run rather than a project.

---

## 10.3 · Measuring similarity

Three metrics. You'll use one.

### Cosine similarity

Measures the **angle** between two vectors, ignoring their length.

```
        ▲
        │      ╱ B
        │    ╱
        │  ╱ θ
        │╱________▶ A

    similarity = cos(θ)
```

Range: **−1 to 1.** In practice with modern models, almost everything lands between 0 and 1,
because these spaces are anisotropic — vectors cluster in a cone rather than spreading evenly.
A "low" similarity is often 0.6, not 0.

| Score | Roughly means |
|---|---|
| 1.0 | Identical direction |
| 0.9+ | Near-paraphrase, or the same topic |
| 0.7–0.9 | Related |
| 0.5–0.7 | Loosely related |
| < 0.5 | Probably unrelated |

> **Those ranges are not portable.** Every model has its own distribution. A 0.82 from one
> model may mean something entirely different from a 0.82 from another. **Never hardcode a
> similarity threshold you haven't calibrated on your own data with your own model** — and
> recalibrate whenever you change either. This is one of the most common production bugs in
> retrieval systems.

### Dot product

Like cosine but sensitive to magnitude. If your vectors are **normalised** to unit length —
most modern embedding models do this for you — dot product and cosine are mathematically
identical, and dot product is faster to compute.

```python
import numpy as np

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def cosine_normalised(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))          # only valid if both are unit length
```

**The practical move:** normalise once at index time, then use dot product everywhere. You get
cosine semantics at dot-product speed. Check whether your model already normalises — many do,
and normalising twice is harmless but knowing matters.

### Euclidean distance

Straight-line distance. Rarely used for text, because magnitude in these spaces tends to
encode things you don't care about (like text length) rather than meaning.

### Which to use

**Cosine, or dot product on normalised vectors.** That's the answer for text retrieval. The
only thing that matters is being *consistent* — the metric you index with must be the metric
you query with, and every vector database makes you declare this at index creation.

---

## 10.4 · What the space looks like

Three properties worth knowing, because each explains a behaviour you'll observe.

### 1 · Things cluster

Similar documents form neighbourhoods. Reduce a real corpus to two dimensions and you'll see
visible clumps — support tickets here, API docs there, marketing copy over there.

This is useful beyond search: clustering embeddings is a cheap way to *discover* the structure
of a corpus you don't know well. Run it on your documents before designing anything. It often
reveals that your corpus contains three kinds of document when you assumed one.

### 2 · Direction carries meaning

The classic:

```
    vector("king") − vector("man") + vector("woman")  ≈  vector("queen")
```

Modern sentence embeddings are messier than this suggests, but the principle holds: consistent
semantic relationships correspond to consistent directions.

### 3 · The space is anisotropic

Embeddings do **not** spread evenly across the space. They occupy a narrow cone, which is why
unrelated texts still score 0.6 rather than 0.

Two consequences you will actually hit:

- **Absolute scores are nearly meaningless.** Rankings are what matter. "Which is closest?" is
  a good question; "is this above 0.75?" usually isn't.
- **Score gaps are informative.** If your top result scores 0.89 and your second scores 0.61,
  that gap is a real signal. If the top ten all score between 0.78 and 0.81, your retrieval is
  telling you it has no idea, and you should treat that as a "no confident answer" condition.

---

## 10.5 · What embeddings miss

**The most important section in this chapter.** Every item here is a production failure mode,
and each one is a reason for something later in Part III.

### 1 · Negation

```
"The medication is safe during pregnancy."
"The medication is NOT safe during pregnancy."
                                    → typically > 0.95 similarity
```

Embedding models are trained on topical relatedness. These sentences are maximally related by
topic. The logical inversion — the only thing that matters — barely registers.

Others in the same family: "increased" versus "decreased", "approved" versus "rejected",
"before" versus "after", "must" versus "must not".

**Mitigations:** retrieve more candidates and let a reranker or the language model itself sort
out polarity (Chapter 13); never let vector similarity alone drive a decision with
consequences.

### 2 · Exact identifiers

```
Query:  "error code E4471"
```

Embeddings represent `E4471` as fragmented tokens with no special status. `E4471` and `E4472`
are near-identical vectors. So are order numbers, SKUs, version numbers, dates, phone numbers,
and legal citations.

**This is the single strongest argument for hybrid search.** Keyword search handles exact
identifiers perfectly, because exact matching is exactly what it does. Chapter 13 combines the
two, and this failure is why.

### 3 · Numbers and quantities

```
"revenue grew 3%"   vs   "revenue grew 30%"        → very similar vectors
"under 10 employees" vs  "over 10,000 employees"   → very similar vectors
```

Numerical magnitude is essentially invisible. If your queries involve comparisons, ranges or
thresholds, that logic belongs in **metadata filters**, not in the vector — which is why
Chapter 12 spends time on filtering.

### 4 · Rare and domain-specific terms

If your organisation calls a thing a "Blorptastic Widget," a general embedding model has never
seen it, will tokenize it into fragments, and will place it somewhere arbitrary. The same
applies to internal project names, uncommon medical or legal terminology, and newly coined
industry jargon.

**Mitigations:** hybrid search (the exact term matches lexically), a glossary that expands
terms at query time, or a fine-tuned embedding model if the domain gap is severe.

### 5 · Structure and position

A vector is one point. It has no notion that this sentence was in the conclusion, that this
paragraph sat under a particular heading, or that this table cell belonged to a specific row.
Everything is flattened.

**Mitigation:** preserve structure in metadata and in the chunk text itself — that's Chapter
11's central concern.

### 6 · Long documents

Every embedding model has a maximum input length, and text beyond it is silently truncated —
usually with no warning. Even within the limit, averaging a very long text into one vector
blurs it into mush: a 5,000-word document about fourteen topics produces a vector that is
strongly about none of them.

**This is the entire reason chunking exists**, and it's the whole of Chapter 11.

### The pattern

> Embeddings capture **topical similarity**. They do not capture logic, identity, magnitude,
> structure, or precision.
>
> Every one of the six failures above is a case of asking a topic-similarity tool to do
> something else. Build systems that use embeddings for what they're good at — *"what is this
> about?"* — and something else for everything else.

---

## 10.6 · Symmetric versus asymmetric search

A distinction most tutorials skip entirely, and it quietly halves the quality of a lot of RAG
systems.

**Symmetric search** compares two things of the same kind: "find articles similar to this
article", "is this ticket a duplicate of that one?" Both sides look alike.

**Asymmetric search** compares a short question against a long passage that *answers* it:

```
Query:    "how do I reset my password"                          (8 tokens, a question)
Document: "To restore access to your account, navigate to        (60 tokens, a procedure)
           Settings, select Security, and choose Reset
           Credentials. A confirmation email will be sent..."
```

These texts do not look alike. One is interrogative and short, the other declarative and long.
They don't even share vocabulary. Naive similarity between them is often mediocre — and
retrieval is *almost always* this shape.

Three ways to handle it, which you can combine:

**1 · Use a model trained for it.** Many embedding models are trained specifically on
question/passage pairs and are far better at this. Check the model card — this is one of the
most consequential selection criteria and one of the least examined.

**2 · Use the model's prefixes.** Several models expect an instruction prefix telling them
which side they're embedding:

```python
query_vec = embed("query: how do I reset my password")
doc_vec   = embed("passage: To restore access to your account...")
```

Forgetting these prefixes — or applying the wrong one — measurably degrades results, silently.
Read the model card.

**3 · Transform the query.** Instead of embedding the question, embed a *hypothetical answer*
to it. Generate a plausible answer with a language model, embed that, and search with it. The
hypothetical answer looks much more like a real passage than the question did.

This is called **HyDE** (Hypothetical Document Embeddings), and you'll implement it in
Chapter 13. It converts an asymmetric problem into a symmetric one, which is a lovely piece of
engineering.

---

## 10.7 · Choosing a model

Six criteria, roughly in order of how much they matter.

| Criterion | What to think about |
|---|---|
| **Task fit** | Trained for retrieval (asymmetric) or just similarity? The most important question and the least asked |
| **Max input length** | 512 tokens is common and small. Your chunking strategy must respect it |
| **Dimensions** | More isn't automatically better. 1024 is a good default; higher costs storage and search time |
| **Domain** | Generic models are weak on specialised vocabulary. Test on *your* text |
| **Language** | Multilingual models trade some English quality for coverage. Only pay that if you need it |
| **Cost and latency** | Matters at index time (millions of chunks) and query time (every request) |

### On dimensions

```
 384 dims → 1.5 KB/vector →  1.5 GB per million → fast search, less nuance
1024 dims → 4.0 KB/vector →  4.0 GB per million → good default
3072 dims → 12 KB/vector  → 12.0 GB per million → slower, marginal gains
```

Quality does not scale linearly with dimensions. Going from 384 to 1024 usually helps
noticeably; 1024 to 3072 usually helps very little while tripling storage and slowing search.
Some models support **Matryoshka** truncation — trained so you can cut the vector short and
keep most of the quality. Worth looking for.

### On leaderboards

Public embedding benchmarks are genuinely useful for building a shortlist and genuinely
misleading if you stop there.

**Why:** benchmarks aggregate across many tasks and domains, none of which is yours. A model
ranked third overall may be first on *your* corpus. Benchmark results also get optimised for,
which erodes their meaning over time.

> **Use a leaderboard to pick three candidates. Then evaluate them on your own data with your
> own queries.** That evaluation is Chapter 14, and it is the only selection method that
> actually answers the question.

---

## 10.8 · Embedding at scale

Indexing a corpus means embedding hundreds of thousands of chunks. The naive loop will take
days and hit every rate limit you have.

### Batch

Embedding APIs accept many texts per call. This is usually a 10–50× speedup for free:

```python
async def embed_batch(texts: list[str], batch_size: int = 96) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        out.extend(await embedding_client.embed(texts[i : i + batch_size]))
    return out
```

### Bound the concurrency

Chapter 4's `Semaphore`, which you now need for real:

```python
sem = asyncio.Semaphore(5)

async def embed_chunk_batch(batch: list[str]) -> list[list[float]]:
    async with sem:
        return await embedding_client.embed(batch)

batches = [chunks[i : i + 96] for i in range(0, len(chunks), 96)]
results = await asyncio.gather(*(embed_chunk_batch(b) for b in batches),
                               return_exceptions=True)
```

`return_exceptions=True` matters here: one failed batch out of 900 should not destroy an hour
of work.

### Cache aggressively

Embedding the same text twice is pure waste, and it happens constantly — re-indexing after a
small change, duplicate content across documents, boilerplate footers.

```python
import hashlib

def cache_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}|{text}".encode()).hexdigest()
```

Persist this. On a re-index where 95% of content is unchanged, a persistent embedding cache
turns a four-hour job into a ten-minute one.

### Make it resumable

Embedding a large corpus takes hours. It **will** be interrupted — a network blip, a rate
limit, a laptop lid. Write progress incrementally and support resuming from where you stopped.
Discovering this requirement at hour three of a four-hour run is a memorable way to learn it.

### Consider batch pricing

From section 9.6: asynchronous batch processing runs at roughly half price. Indexing a corpus
is the definitive latency-insensitive workload. If your provider offers it, use it.

---

## 10.9 · Build it

**A semantic search engine over your own documents.** Small, and the foundation of everything
in Part III.

```
src/genai_toolkit/embeddings/
├── protocol.py      EmbeddingModel Protocol  ← swappable, like Chapter 6's LLMClient
├── provider.py      a real implementation
├── local.py         a sentence-transformers implementation
├── cache.py         persistent cache keyed by (model, text hash)
├── batch.py         batching, bounded concurrency, resumable progress
└── similarity.py    cosine / dot product, top-k
```

Requirements:

1. Embed a folder of documents (use Project A's chunker for now — Chapter 11 improves it).
2. Store vectors plus metadata on disk. NumPy array plus a JSONL sidecar is fine; Chapter 12
   replaces this with a real database.
3. Search: embed the query, score every chunk, return top-k with scores.
4. **Two interchangeable models** behind the Protocol — a hosted one and a local one.
5. Persistent caching, bounded concurrency, resumable indexing.
6. A CLI: `index <folder>`, `search <query> --k 5`, `stats`.
7. `make check` green.

### Then run these experiments — this is the real work

**1 · The negation test.** Index both pregnancy sentences from section 10.0. Search the
question. Record the two similarity scores and how far apart they are. **Do this first.** It
will permanently change how much you trust a vector score.

**2 · Map your score distribution.** Take 50 queries. Record the top-1 similarity for each.
Plot the distribution. Now you know what "high" and "low" mean *for your model on your data* —
which is the only calibration that means anything.

**3 · Symmetric versus asymmetric.** Compare: question → passage, question → question, passage
→ passage. Note how much lower the first one scores. That gap is why HyDE exists.

**4 · Compare two models.** Same corpus, same 20 queries, two embedding models. Where do they
disagree? Which is right? *(You'll formalise this in Chapter 14; do it by eye now.)*

**5 · Find the truncation cliff.** Embed a document at 100, 500, 1,000 and 5,000 tokens. Search
for something that appears only at the end. Find the length at which it stops being findable.
That number is your model's real usable limit, and it's often lower than advertised.

**6 · Break it with an identifier.** Index a document containing `E4471` and another containing
`E4472`. Search for one. Observe that vector search cannot reliably tell them apart. **This is
the experiment that makes Chapter 13 feel necessary rather than optional.**

**7 · Cluster your corpus.** Reduce your embeddings to 2D and plot them. Look at the clusters.
Do they match what you expected your corpus to contain? They often don't, and the surprise is
valuable.

---

## 10.10 · Exercises

**1 · Implement cosine from scratch.** With NumPy, then without NumPy in pure Python. Verify
they agree. Time both on 10,000 vectors. Understand why NumPy is 100× faster.

**2 · Normalisation check.** Determine empirically whether your model returns unit vectors —
compute the norm of ten embeddings. Then verify that dot product and cosine agree for
normalised vectors and disagree for unnormalised ones.

**3 · Threshold calibration.** Build a set of 30 query/document pairs, hand-labelled relevant
or not. Find the similarity threshold that best separates them. Then run the same procedure
with a second model and observe that the threshold is completely different.

**4 · Dimension tradeoff.** If your model supports truncation, measure retrieval quality at
full, half and quarter dimensions. Plot quality against storage. Find your knee.

**5 · A cache that earns its keep.** Index a 1,000-chunk corpus. Change one document. Re-index.
**Measure the time and cost with and without your cache.** Report the ratio.

**6 · Batch size sweep.** Measure embedding throughput at batch sizes 1, 8, 32, 96, 256. Plot
it. Find where it plateaus, and note where you start hitting errors.

**7 · Query expansion.** For 10 queries, generate three paraphrases with a language model, embed
all four, and average the vectors. Does retrieval improve? *(A cheap preview of Chapter 13.)*

**8 · Find your domain gap.** Collect 20 terms specific to your domain. Check whether
semantically-related pairs of them are actually close in vector space. Quantify how badly a
generic model handles your vocabulary.

---

## 10.11 · Checkpoint

> **Move on to Chapter 11 when all of these are true.**

**Explain, out loud:**

1. What an embedding is, and how the model learned to produce it.
2. Why the two pregnancy sentences score above 0.95, in terms of training objective.
3. The six things embeddings miss, with an example of each.
4. Why absolute similarity scores are nearly meaningless and gaps are informative.
5. What asymmetric search is, and three ways to handle it.
6. Why switching embedding models forces a full re-index.
7. Why you must not trust a public leaderboard as your final selection criterion.

**Write from memory:**

8. Cosine similarity, and the normalised dot-product shortcut.
9. A batched, concurrency-bounded, cached embedding pipeline.
10. A top-k search over an in-memory vector store.

**Verify:**

11. You have run the negation experiment and recorded the scores.
12. You have plotted your own similarity distribution and know your model's real ranges.
13. You have demonstrated the identifier failure with `E4471` / `E4472`.
14. Two embedding models are swappable in your code without touching the search logic.

Number 11 and number 13 are the ones that matter. If you haven't *seen* embeddings fail, you
will over-trust them, and Chapter 13 will feel like unnecessary complexity instead of the
obvious fix.

---

## 10.12 · Going deeper (optional)

**[Appendix B · Vector Mathematics](../../appendices/)** — dot products, norms, cosine, and
why high-dimensional spaces behave counter-intuitively. Genuinely interesting, entirely
optional.

**If you want one paper:** look up the Sentence-BERT paper. It explains why you can't just
average a language model's token embeddings and expect good sentence similarity, and why
retrieval models need their own training objective. Short, readable, and it clarifies the
whole field.

**If you want to see the space:** search for embedding projector tools that let you load your
own vectors and explore them in 3D. Spending twenty minutes rotating your own corpus teaches
intuition that no amount of reading will.

**If you want the frontier:** read about **late interaction** retrieval (ColBERT and its
descendants), which keeps a vector per token instead of one per document. It's more expensive
and substantially better at exactly the precision problems in section 10.5 — worth knowing
exists.

---

<div align="center">

**[← Project B](../../part-2-language-models/project-b-streaming-assistant/)** · **[The Book](../../readme.md)** · **[Chapter 11 → Document Processing & Chunking](../ch11-chunking/)**

*Chapter 10 of 31 · Week 10 · Part III begins*

</div>
