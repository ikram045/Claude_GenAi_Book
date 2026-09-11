# Chapter 12 · Vector Databases

### Approximate search, the recall you're silently giving up, and the filtering bug nobody warns you about

> **Week 11, part 2 · ~11 hours · Infrastructure and code**
>
> Where your index stops being a NumPy array and becomes a system. Also where two subtle
> failure modes live that will otherwise cost you a week each.

---

## 12.0 · Why this chapter exists

Chapter 10's search worked like this:

```python
scores = embeddings @ query_vector        # compare against EVERY vector
top_k = np.argsort(scores)[-k:][::-1]
```

For 10,000 chunks this is instant. It's also *exactly correct* — it examines every candidate,
so it cannot miss the true nearest neighbour.

Now scale it:

| Chunks | Brute-force query time | Memory |
|---:|---|---|
| 10,000 | ~5 ms | 40 MB |
| 100,000 | ~50 ms | 400 MB |
| 1,000,000 | ~500 ms | 4 GB |
| 10,000,000 | ~5 s | 40 GB |

At a million chunks you're adding half a second to every request, and you haven't called the
model yet. At ten million it's unusable.

So vector databases do something different, and the something is the thing to understand:
**they stop being exact.** They use approximate nearest neighbour search, which is dramatically
faster and **will sometimes miss results your brute-force search would have found.**

Nobody tells you this. The database returns ten results with confident-looking scores and never
mentions that the best match was skipped. This chapter is about knowing that, measuring it, and
controlling it — plus a filtering behaviour that silently returns wrong result counts and is
even easier to miss.

---

## 12.1 · Approximate nearest neighbour

The core bargain:

> **Give up a small amount of accuracy for an enormous amount of speed.**

Instead of comparing against every vector, an ANN index organises vectors so that searching
examines only a promising subset. The result is *usually* the true top-k, and *sometimes* not.

The quality measure is **recall@k**:

```
recall@10 = (how many of the true top-10 the index returned) / 10
```

At recall 0.95, one in twenty of your results is missing something a perfect search would have
found. Whether that matters depends entirely on your application — and you can only decide if
you measure it.

```
    ▲ speed
    │
    │  ●  low recall, very fast
    │      ●
    │          ●
    │              ●  ← the knee: most of the speed, little of the loss
    │                  ●
    │                      ● brute force (recall 1.0, slow)
    └──────────────────────────────▶ recall
```

**Your job is to find the knee, deliberately, with measurement.** Not to accept a default.

---

## 12.2 · Index types

### Flat — no index at all

Brute force. Exact, slow, simple.

**Use it when** you have under ~50,000 vectors, or when you need guaranteed exactness, or as
the **ground truth** for measuring your approximate index. That last use is the important one
and people forget it: you cannot compute recall without something exact to compare against.

### IVF — inverted file

Cluster the vectors into partitions. At query time, search only the nearest few partitions.

```
   ┌────────┬────────┬────────┐
   │ part 1 │ part 2 │ part 3 │
   │  ···   │ ·:·  ✕ │  ···   │   ✕ = query
   ├────────┼────────┼────────┤   search only the nearest N partitions
   │ part 4 │ part 5 │ part 6 │
   └────────┴────────┴────────┘
```

Fast to build, memory-efficient. The failure mode is at partition boundaries: a true neighbour
just across a boundary in an unsearched partition is simply never seen. Tune `nprobe` (how
many partitions to search) to trade recall for speed.

### HNSW — hierarchical navigable small world

The dominant choice, and what you'll use. A multi-layer graph: sparse long-range links at the
top for coarse navigation, dense short-range links at the bottom for precision.

```
  layer 2   ●───────────────────●          coarse hops
              ╲               ╱
  layer 1   ●───●───────●───●───●          medium
             ╲  │      ╱│  ╱
  layer 0   ●─●─●─●─●─●─●─●─●─●─●          every vector, dense links
```

Search enters at the top, greedily hops toward the query, descends a layer, repeats. Excellent
recall-to-speed ratio, and search cost grows roughly logarithmically with corpus size.

Costs: high memory (it stores the graph as well as the vectors), slow to build, and deletions
are awkward (see section 12.7).

### Quantization — compress the vectors

Orthogonal to the index type. Store vectors in less space at some cost in accuracy.

| Method | Compression | Quality impact |
|---|:---:|---|
| None (float32) | 1× | — |
| Scalar (int8) | 4× | Small |
| Product quantization | 10–50× | Moderate |
| Binary | 32× | Large alone — usable with rescoring |

The pattern that makes aggressive quantization work is **two-stage retrieval**: search the
compressed index to get 100 candidates fast, then rescore those 100 against the full-precision
vectors. You get most of the memory saving and nearly all of the accuracy, because the
expensive exact comparison runs on 100 vectors instead of ten million.

---

## 12.3 · HNSW parameters

Three knobs. Understand them once and you'll tune every vector database the same way.

| Parameter | When | Effect | Typical |
|---|---|---|---|
| **`M`** | Build | Links per node. Higher = better recall, more memory, slower build | 16–64 |
| **`ef_construction`** | Build | Effort during build. Higher = better graph, much slower build | 100–400 |
| **`ef_search`** | **Query** | Candidates explored. Higher = better recall, slower query | 40–400 |

The crucial practical point:

> **`ef_search` is a query-time parameter.** You can change it per request without rebuilding
> anything. `M` and `ef_construction` are baked in at build time and changing them means
> reindexing.

This gives you a tuning strategy: set `M` and `ef_construction` reasonably (32 and 200 are
sensible), then tune `ef_search` empirically against a recall measurement. If you need more
recall later, you raise a number. If you'd chosen badly on `M`, you'd be rebuilding.

You can also vary `ef_search` per query — high for a precision-critical route, low for a
latency-critical one. Few people exploit this.

---

## 12.4 · Metadata filtering, and the bug

Filtering is essential in real systems: search only current documents, only this customer's
data, only this document type.

```python
results = store.search(
    query_vector=qv,
    k=10,
    filter={"document_type": "policy", "updated_at": {"$gte": "2025-01-01"}},
)
```

**How the database combines the filter with the vector search determines whether your results
are correct.** There are three approaches, and the difference matters enormously.

### Post-filtering — the one that breaks

```
1. Vector search → top 100 candidates
2. Apply the filter → keep whatever survives
3. Return the top 10 of those
```

The failure: **if the filter is selective, you get fewer than 10 results — possibly zero — even
though thousands of matching documents exist.**

```
Search: "refund policy", filter: customer_id = "acme-corp"

Top 100 by vector similarity  → 99 belong to other customers
After filtering               → 1 result
Actual matching documents     → 340
```

The database returned one result. It reported no error. Your answer is built on 1/10th of the
available evidence, and nothing in the response indicates that.

This is a genuinely nasty bug because it's **silent and load-dependent**: it works fine in
testing with three customers and degrades as your corpus grows.

### Pre-filtering — correct, sometimes slow

```
1. Apply the filter → the matching subset
2. Vector search within that subset only
```

Always returns k results if k exist. The cost is that a highly selective filter can produce a
subset the ANN index can't search efficiently, so some systems fall back to brute force —
correct, but slower.

### Filtered search — what good databases do

Apply the filter *during* graph traversal, skipping non-matching nodes as it walks. Correct and
fast. Most mature vector databases do this now; the details of how well vary considerably under
highly selective filters.

> **Find out which one your database does, and test it.** Index 10,000 vectors where only 20
> match a filter. Search with `k=10`. If you get fewer than 10 results, you have post-filtering
> and you need to know that before it reaches production.
>
> This is a five-minute test that has saved people weeks.

---

## 12.5 · Choosing a store

An honest comparison. The correct choice is more often about your existing infrastructure than
about benchmark numbers.

### pgvector — Postgres with a vector extension

**Choose it when** you already run Postgres, which is most teams.

The advantage is not performance. It's that **your vectors live in the same database as your
metadata, with real transactions and real joins**:

```sql
SELECT c.text, c.heading_path, d.title, d.updated_at,
       c.embedding <=> %(query)s AS distance
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.customer_id = %(customer)s
  AND d.updated_at > NOW() - INTERVAL '1 year'
  AND NOT d.archived
ORDER BY distance
LIMIT 10;
```

One query. Joined metadata, transactional consistency with the rest of your application, one
backup story, one set of credentials, one thing to operate. A dedicated vector database means
keeping two systems in sync — and **sync bugs are the most common operational problem in
retrieval systems**: a document deleted in Postgres and still present in the vector store will
keep being retrieved and cited.

Limits: at tens of millions of vectors with heavy concurrent load, dedicated engines pull
meaningfully ahead.

### Dedicated vector databases

Qdrant, Weaviate, Milvus and others. Built for this workload: better filtered search, richer
quantization options, horizontal scaling, hybrid search built in.

**Choose one when** you have tens of millions of vectors, need very high query throughput, or
want built-in hybrid search and reranking rather than assembling it yourself.

### In-memory libraries

FAISS and similar. Libraries, not databases — no persistence, no filtering, no concurrency
story. Excellent for experiments, research, and as the exact ground truth for recall
measurement. Not a production store on their own.

### The recommendation

> **Start with pgvector if you have Postgres.** It will take you further than you expect, and
> the operational simplicity is worth real performance.
>
> Move to a dedicated engine when you have a measured reason. "It might not scale" is not a
> measured reason. A p95 latency chart is.

**And put it behind the Protocol you designed in Project A**, so this decision is reversible:

```python
class VectorStore(Protocol):
    async def upsert(self, chunks: list[EmbeddedChunk]) -> None: ...
    async def search(self, vector: list[float], k: int,
                     filter: dict | None = None) -> list[SearchResult]: ...
    async def delete_document(self, document_id: str) -> int: ...
```

That's the interface Project A anticipated. This is the chapter where the anticipation pays
off.

---

## 12.6 · Schema design

```sql
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,
    source_path     TEXT NOT NULL,
    title           TEXT,
    document_type   TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    version         TEXT,
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL,
    archived        BOOLEAN NOT NULL DEFAULT FALSE,
    metadata        JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE chunks (
    id              BIGSERIAL PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    display_text    TEXT NOT NULL,      -- shown to users
    embedding_text  TEXT NOT NULL,      -- enriched, what was embedded (11.8)
    heading_path    TEXT[],
    page_number     INT,
    char_start      INT NOT NULL,
    char_end        INT NOT NULL,
    token_count     INT NOT NULL,
    content_hash    TEXT NOT NULL,
    embedding       VECTOR(1024),
    embedding_model TEXT NOT NULL,      -- ← the field people forget
    tsv             TSVECTOR,           -- for keyword search (Chapter 13)
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 32, ef_construction = 200);

CREATE INDEX ON chunks USING GIN (tsv);
CREATE INDEX ON chunks (document_id);
CREATE INDEX ON documents (document_type, updated_at) WHERE NOT archived;
```

Four details that matter:

**`ON DELETE CASCADE`** — deleting a document removes its chunks. Orphaned chunks are the
number one cause of "why is it citing a document we deleted?"

**`embedding_model`** — record which model produced each vector. When you migrate models
(section 10.2), this is what lets you find the stale ones and re-embed incrementally instead of
wiping everything.

**`display_text` and `embedding_text` separately** — section 11.8's enriched text is for
embedding; the original is for showing. Keep both.

**`tsv`** — the full-text search column. You don't need it yet. You will in Chapter 13, and
adding it now costs nothing while backfilling it over ten million rows later costs an outage
window.

---

## 12.7 · Operations

The part tutorials skip entirely, and where production time actually goes.

### Upsert, don't insert

Re-indexing is normal — documents change, chunkers improve, models get swapped. Make it
idempotent:

```sql
INSERT INTO chunks (document_id, chunk_index, display_text, embedding, ...)
VALUES (...)
ON CONFLICT (document_id, chunk_index)
DO UPDATE SET display_text = EXCLUDED.display_text,
              embedding    = EXCLUDED.embedding,
              content_hash = EXCLUDED.content_hash;
```

### Deletion is harder than it looks

In HNSW, removing a node would break the graph. So most implementations mark deleted vectors as
**tombstones** — they're skipped at query time but still occupy memory and still get traversed.

Consequences worth knowing:

- Heavy deletion degrades performance over time.
- Deleted vectors keep consuming memory until you rebuild.
- Some engines auto-compact; others need a manual reindex.

**If your corpus churns significantly, schedule periodic reindexing.** A system that deletes
30% of its documents monthly and never rebuilds gets slower every month for reasons nobody
diagnoses.

### Update the document, not the chunk

When a document changes, chunk boundaries shift. Chunk 7 of the new version is not chunk 7 of
the old one. **Delete all chunks for the document and re-insert**, in a transaction:

```python
async def reindex_document(doc: ExtractedDocument) -> None:
    async with db.transaction():
        await db.execute("DELETE FROM chunks WHERE document_id = $1", doc.id)
        await db.executemany(INSERT_CHUNK, new_chunk_rows)
```

The transaction matters. Without it, a crash between delete and insert leaves a document
present in your metadata table and absent from search — which looks like a retrieval bug and
isn't.

### Skip what hasn't changed

```python
if existing_hash == doc.content_hash:
    return                      # nothing to do
```

With section 10.8's embedding cache, a re-index over a corpus where 2% changed should take 2%
of the time. If it doesn't, you're re-embedding unchanged content and paying for it.

### Migrating embedding models

The operation that frightens people, done properly:

1. Add a second vector column for the new model.
2. Backfill in batches, in the background, at batch pricing. Nothing is disrupted.
3. Run both indexes in parallel and **compare retrieval quality** on your eval set (Chapter 14).
4. Switch reads to the new column.
5. Drop the old column once you're confident.

Zero downtime, and — crucially — you have *evidence* that the new model is better rather than a
hope.

---

## 12.8 · Scale and cost

Rough figures at 1,024 dimensions, float32:

```
Vector storage:     4 KB per vector
HNSW graph:         ~1.5–2× the vector size, in memory
Text and metadata:  1–3 KB per chunk

1M chunks   ≈  4 GB vectors +  ~7 GB graph  →  fits comfortably on one machine
10M chunks  ≈ 40 GB vectors + ~70 GB graph  →  a large machine, or sharding
100M chunks                                  →  a distributed system and a real budget
```

Three reflexes worth having:

- **Quantize before you shard.** int8 quantization cuts memory 4× for a small quality cost.
  Sharding multiplies your operational complexity. Try the cheap lever first.
- **Most corpora are smaller than people assume.** A company wiki is often under 100,000
  chunks. Ten million chunks is a lot of documents. Don't architect for a scale you won't reach.
- **Query cost is dominated by the model, not the database.** A vector search is single-digit
  milliseconds; the language model call is hundreds. Optimise accordingly.

---

## 12.9 · Build it

Replace Chapter 10's NumPy store with a real one.

```
src/genai_toolkit/stores/
├── base.py          VectorStore Protocol
├── memory.py        exact brute force — the GROUND TRUTH for recall
├── pgvector.py      the production store
└── migrations/      schema versions
```

Requirements:

1. **The Protocol from section 12.5**, with at least two implementations.
2. **The full schema** from section 12.6, including `tsv` and `embedding_model`.
3. **Idempotent upserts**, and transactional document-level reindexing.
4. **Metadata filtering** — type, date range, tags, archived status.
5. **A recall harness**: measure recall@k of your ANN index against the exact in-memory store
   on the same data.
6. **Configurable `ef_search` per query.**
7. **Incremental reindexing** that skips unchanged documents by hash.
8. **An orphan check**: assert no chunk exists without a document. Run it in CI.
9. `make check` green.

### The experiments — this is the actual learning

**1 · Measure your recall.** Index 100,000 vectors. Run 200 queries against both the exact
store and the HNSW index. Compute recall@10. **Write the number down.** Most engineers using a
vector database have never done this and cannot tell you their recall.

**2 · Sweep `ef_search`.** Values from 10 to 500. Plot recall against latency. Find the knee.
Choose a value and be able to defend it.

**3 · Reproduce the post-filtering bug.** Index 10,000 vectors where exactly 20 match a filter.
Search with `k=10`. Count what comes back. If it's fewer than 10, you now understand section
12.4 in your bones. Test your chosen database this way before trusting it.

**4 · Feel the deletion cost.** Index 100,000 vectors, measure query latency, delete 30%,
measure again. Then rebuild the index and measure a third time.

**5 · Quantization tradeoff.** If your store supports it, measure recall and memory at
float32, int8, and binary-with-rescoring. Decide what you'd ship.

**6 · Filter selectivity curve.** Measure query latency with filters matching 100%, 10%, 1% and
0.01% of the corpus. Most implementations have a nasty region somewhere in there. Find yours.

---

## 12.10 · Exercises

**1 · HNSW by hand.** Implement a toy HNSW with 1,000 vectors — build the layers, do greedy
search. It'll be slow and wrong at the edges, and you will never be confused about `ef_search`
again.

**2 · The exact/approximate diff.** For 100 queries, log which results the ANN index missed
relative to exact search. Read those cases. Is there a pattern — are missed results
systematically lower-scoring, or is it random?

**3 · Two-stage retrieval.** Implement search-then-rescore: retrieve 100 from a quantized index,
rescore against full-precision vectors, return 10. Measure recall and latency against the
one-stage version.

**4 · The sync bug, demonstrated.** Build a system where documents live in Postgres and vectors
in a separate store. Delete a document from one and not the other. Show the stale citation.
**Then fix it** — and note how much easier it would have been in one database.

**5 · Zero-downtime model migration.** Add a column, backfill, compare, switch, drop. Measure
retrieval quality before and after on the same queries.

**6 · Index build economics.** Time an HNSW build at `ef_construction` of 50, 100, 200, 400.
Measure resulting recall. Plot build time against recall and find where it stops paying.

**7 · Metadata filter design.** Take 20 realistic queries from your domain. For each, decide
which should use a filter and which shouldn't. Implement the filters. Measure the quality
difference. *(Hint: "recent documents only" is not always the right filter.)*

**8 · Capacity plan.** For a corpus you care about, compute storage, memory and monthly cost at
1M, 10M and 100M chunks — with and without quantization. **At which point would you change
architecture, and to what?**

---

## 12.11 · Checkpoint

> **Move on to Chapter 13 when all of these are true.**

**Explain, out loud:**

1. What ANN trades away, and why nobody tells you.
2. How HNSW searches, and what each of the three parameters controls.
3. Why `ef_search` is special among those three.
4. Pre-filtering versus post-filtering, and the exact failure post-filtering produces.
5. Why deleting from an HNSW index degrades it, and what to do about that.
6. Why pgvector's real advantage is joins and transactions rather than speed.
7. Why you delete and re-insert all of a document's chunks rather than updating them.

**Write from memory:**

8. The `VectorStore` Protocol.
9. A schema with HNSW and GIN indexes and cascading deletes.
10. An idempotent upsert.
11. A recall@k measurement against an exact baseline.

**Verify:**

12. **You know your index's recall@10 as a number.**
13. You have an `ef_search` sweep plot and a defended choice.
14. You have tested your database's filtering behaviour with a highly selective filter.
15. Your reindex skips unchanged documents, and your orphan check runs in CI.

Number 12 is the one. If you can't state your recall, you don't know whether your retrieval
system works — you only know it returns results.

---

## 12.12 · Going deeper (optional)

**Read the HNSW paper** (Malkov & Yashunin). Unusually readable for an algorithms paper, with
good diagrams. You'll finish it understanding exactly what `M` does.

**Read your database's filtering documentation carefully.** Specifically: does it filter during
traversal, and how does it behave when the filter is highly selective? This is the least
documented and most consequential difference between engines.

**If you're curious about quantization:** look up product quantization and binary quantization
with rescoring. The two-stage pattern is elegant and appears all over systems engineering.

**If you want to see how far one machine goes:** search for benchmarks of pgvector at 10M+
vectors. The numbers are usually better than people expect, and the operational simplicity
argument gets stronger the more you read.

---

<div align="center">

**[← Chapter 11](../ch11-chunking/)** · **[The Book](../../readme.md)** · **[Chapter 13 → Search That Actually Works](../ch13-search-that-works/)**

*Chapter 12 of 31 · Week 11*

</div>
