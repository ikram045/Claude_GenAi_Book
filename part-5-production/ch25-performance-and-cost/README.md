# Chapter 25 · Performance & Cost

### From "I measured one request" to "I run this at scale and the bill is predictable"

> **Week 25, part 1 · ~11 hours**
>
> Chapter 9 taught you the economics of a single request and a five-step optimisation ladder.
> This chapter is what changes when there are a hundred thousand requests, several routes, and
> someone in finance with a question.

---

## 25.0 · Why this chapter exists

Chapter 9 got you from $3,150/month to $558 on one workload. Everything there still applies —
caching first, then context trimming, then routing, then output length, then a response cache.

Three things change at production scale:

**You have data now.** Chapter 23 gave you traces. You no longer estimate where the money goes;
you query it. **Profiling replaces guessing**, and the answer is usually not what anyone
predicted.

**Load changes the picture.** Connection pools, rate limits, queueing, and the question of what
happens when demand exceeds capacity. A system that's fast at one request per second can be
unusable at fifty.

**Cost becomes governance.** Not "make it cheaper" but "keep it predictable, attribute it to
teams, and stop one bad deploy from spending a month's budget in a night."

---

## 25.1 · Profile from your traces

Stop estimating. You have the data.

```sql
-- Where the money actually goes
SELECT route,
       count(*) AS requests,
       sum(cost_usd) AS total,
       sum(cost_usd) / count(*) AS per_request,
       sum(input_tokens) AS input,
       sum(output_tokens) AS output,
       sum(cache_read_tokens)::float / nullif(sum(input_tokens + cache_read_tokens), 0) AS cache_rate
FROM traces
WHERE ts > now() - interval '7 days'
GROUP BY route
ORDER BY total DESC;
```

Four questions to answer before you change anything:

1. **Which route dominates spend?** It's rarely the one people worry about.
2. **What's the input/output split per route?** Section 9.3 said input usually dominates in RAG.
   Verify it for *your* system.
3. **What's the cache hit rate per route?** A route at zero is leaving the biggest free win on
   the table.
4. **What does the expensive tail look like?** Pull the most expensive 1% of requests and read
   ten traces. There's usually one pattern.

### The tail is where the surprises are

```
   cost per request

   p50    $0.004
   p90    $0.011
   p99    $0.089        ← 22× the median
   max    $0.940
```

A p99 at twenty times the median usually means one of: agent runs hitting the iteration cap, a
retrieval path returning far more context than intended, conversations that grew unbounded, or
one user doing something unusual.

**Every one of those is fixable, and each is invisible in the average.** Read the traces.

---

## 25.2 · The caching stack

Chapter 9 covered prompt caching. In production you want four layers, because they catch
different things.

```
   request
      │
   ┌──▼──────────────────┐
   │ 1 · exact response  │  hash(model, system, messages) → response
   └──┬──────────────────┘  hit: FREE, ~1ms
      │ miss
   ┌──▼──────────────────┐
   │ 2 · semantic cache  │  embed query → find a near-identical past query
   └──┬──────────────────┘  hit: one embedding call, ~20ms
      │ miss
   ┌──▼──────────────────┐
   │ 3 · embedding cache │  hash(model, text) → vector
   └──┬──────────────────┘  saves re-embedding at index and query time
      │
   ┌──▼──────────────────┐
   │ 4 · prompt cache    │  provider-side, ~10% of input price
   └──┬──────────────────┘
      │
    the model
```

### Layer 1 · Exact response cache

Free on a hit. 10–20% of traffic in most support and documentation systems.

```python
key = sha256(f"{model}|{system_version}|{normalise(messages)}".encode()).hexdigest()
```

**Include the system prompt version in the key.** Otherwise a prompt change serves stale answers
from the old prompt, and you'll spend a day confused about why your improvement didn't show up.

**Invalidate on corpus change.** A RAG answer cached before a document update is wrong. Version
your corpus and include that in the key too.

**Never cache anything personalised.** If the answer depends on who's asking, the cache key must
include them — or don't cache it.

### Layer 2 · Semantic cache

Catches paraphrases that the exact cache misses:

```
"how do I cancel my subscription"   ← cached
"how can I cancel my subscription"  ← exact cache misses, semantic cache hits
```

```python
async def semantic_lookup(query: str, threshold: float) -> str | None:
    vec = await embed(query)
    hit = await cache_index.search(vec, k=1)
    if hit and hit[0].score >= threshold:
        return hit[0].response
    return None
```

> **Set the threshold high, and calibrate it (section 10.3).** A semantic cache that's too loose
> serves the answer to a *similar but different* question, which is a correctness bug that looks
> like a caching bug and is very hard to notice. Start conservative — well above where you think
> the line is — and measure false-hit rate on real traffic before loosening it.

### Layer 3 · Embedding cache

From section 10.8. Enormous at index time, useful at query time for repeated queries. Persist it.

### Layer 4 · Prompt cache

Section 9.4. **Monitor the hit rate as a first-class metric** (section 23.7) — it fails silently,
and silent failures in the layer that saves you 90% are expensive.

---

## 25.3 · Routing, done with evidence

Section 9.6 introduced model routing. At production scale, do it properly.

### Route on measured difficulty, not on guesses

```python
class Route(BaseModel):
    reasoning: str
    complexity: Literal["simple", "moderate", "complex"]
    needs_retrieval: bool
    needs_tools: bool
```

Then the important part: **run your eval suite on each route independently.**

| Route | Traffic | Model | Effort | Eval score | $/req |
|---|---:|---|---|---:|---:|
| identifier lookup | 18% | Haiku | low | 0.96 | 0.0004 |
| simple factual | 42% | Haiku | medium | 0.91 | 0.0011 |
| complex / multi-hop | 31% | Opus | high | 0.89 | 0.0068 |
| agentic | 9% | Opus | xhigh | 0.83 | 0.0412 |

**A router that quietly degrades 42% of your answers is not a saving.** That per-route eval
column is what makes the routing defensible, and it's what an interviewer will ask about.

### Three cautions

**Lower effort before a cheaper model.** Section 9.6's reasoning: caches are model-scoped, so a
cascade forfeits cache reuse across its models. On newer models, low effort often matches a
previous generation at high effort — and you keep one cache namespace. Measure both.

**The router costs something.** A classification call adds tokens and latency to *every* request.
For identifier-shaped queries, a regex is free and just as accurate.

**Judge cost per completed task.** A cheaper route that sends users back for a second turn isn't
cheaper (section 9.7).

---

## 25.4 · Latency at scale

### The budget

Decide what the user experiences, then work backwards:

```
   Target: first token within 800ms

   network in            50ms
   auth + routing        30ms
   query rewriting      180ms   ← a full model call. Can it be skipped for simple queries?
   retrieval            120ms
   reranking            250ms   ← the biggest fixed cost
   prompt assembly       10ms
   TTFT from model      410ms
   ─────────────────────────
   total              1,050ms   ← over budget
```

That decomposition tells you exactly where to cut. Options, in order:

- **Skip stages for simple queries.** Identifier lookups need no rewriting and no reranking.
- **Parallelise.** Run retrieval while the rewrite is in flight, and discard if the rewrite
  changes the query materially.
- **Cache the rewrite** — conversational rewrites repeat more than you'd think.
- **Rerank fewer candidates.** 50 → 25 often costs little quality and halves the time.
- **Prompt caching** — a cached prefix isn't reprocessed, which shows up in TTFT.

### Streaming hides most of it

Section 9.8's point, worth restating because it's the biggest lever: with streaming, the user
sees the first token at 1,050ms and reads while the rest arrives. Without it, they wait for
everything.

**And you can stream earlier than the answer.** Send status events during retrieval:

```
data: {"type":"status","stage":"searching"}
data: {"type":"status","stage":"reading","sources":5}
data: {"type":"token","text":"Enterprise"}
```

Perceived latency drops again, because something is happening from 200ms.

### Under load

Four things that matter and one that surprises people:

**Connection pooling.** One `httpx.AsyncClient` for the process (section 4.4). A client per
request exhausts sockets and adds TLS handshakes to every call.

**Bounded concurrency.** `Semaphore` on every outbound call. Unbounded concurrency under a
traffic spike is how you get rate-limited across your whole service at once.

**Queue with backpressure.** When demand exceeds capacity, **reject fast rather than queue
forever.** A 503 in 50ms is a better user experience than a 90-second wait ending in a timeout,
and it protects the requests already in flight.

**Timeouts everywhere**, at every layer, with the total bounded.

**The surprise:** your own service is rarely the bottleneck. **Provider rate limits are.** Know
your limits per model, monitor how close you are, and design for what happens when you hit them
— which is the next section.

---

## 25.5 · Graceful degradation

When something fails or you hit a limit, degrade rather than error. In order of preference:

```
   full pipeline
        │ reranker unavailable
   ┌────▼─────────────────────┐
   │ fused results, no rerank │  slightly worse, still good
   └────┬─────────────────────┘
        │ primary model rate-limited
   ┌────▼─────────────────────┐
   │ fall back to another     │  note: different cache namespace
   └────┬─────────────────────┘
        │ everything degraded
   ┌────▼─────────────────────┐
   │ serve from cache, or     │
   │ return retrieval results │  "here are the relevant documents"
   │ with no generated answer │
   └──────────────────────────┘
```

That last tier is underused. **Retrieved passages with no generated answer is a genuinely useful
product** when generation is unavailable — the user gets the source material and can read it.
Far better than an error page.

```python
async def answer_with_degradation(q: str, ctx) -> Answer:
    try:
        results = await retrieve(q)
    except Exception:
        logger.exception("retrieval failed")
        return Answer.unavailable("Search is temporarily unavailable.")

    try:
        results = await rerank(results, timeout=0.5)
    except (TimeoutError, ServiceError):
        logger.warning("reranker unavailable, proceeding unranked")
        ctx.degraded.append("rerank")

    try:
        return await generate(q, results)
    except RateLimitError:
        ctx.degraded.append("generation")
        return Answer.sources_only(results,
            note="Showing relevant sources — answer generation is busy.")
```

**Record what degraded** (`ctx.degraded`) so it appears in traces and metrics. A silent
degradation that persists for a week is a quality regression nobody investigates.

---

## 25.6 · Cost governance

Optimisation makes it cheaper. Governance makes it **predictable**, which is what a business
actually needs.

**Budgets with automatic action.**

```python
@dataclass
class Budget:
    scope: str                     # "global" | "route:chat" | "user:123"
    monthly_limit_usd: float
    alert_at: float = 0.8
    hard_stop_at: float | None = 1.0     # what happens at 100%?
```

Decide *before* you need to: at 100% of budget, do you stop serving, degrade to a cheaper model,
or keep going and alert loudly? All three are valid; none should be discovered at 2am.

**Per-user quotas** stop one user — or one compromised session — consuming everything. This is
also the denial-of-wallet defence from section 24.6.

**Attribution.** Tag every request with route, feature, team and user. When someone asks "why did
the bill double," you answer in one query instead of one week.

**Forecast.** Project monthly spend from a rolling window. Alert on the *trajectory*, not just
the total, so you find out on the 8th rather than the 30th.

---

## 25.7 · Build it

```
src/genai_toolkit/perf/
├── cache/
│   ├── response.py    exact, versioned by prompt + corpus
│   ├── semantic.py    with a calibrated threshold and false-hit tracking
│   └── embedding.py   persistent
├── routing.py         difficulty classification, per-route config
├── degrade.py         the fallback chain, recorded
├── budget.py          budgets, quotas, forecasting
└── profile.py         trace-driven cost and latency reports
```

Requirements:

1. **All four cache layers**, with hit rates as metrics.
2. **The semantic cache threshold calibrated**, with a measured false-hit rate.
3. **Routing with a per-route eval score** — the table from 25.3, from your own data.
4. **A latency budget decomposition** for your main route, measured, with one stage cut by 30%.
5. **The degradation chain**, with degradations recorded in traces.
6. **Backpressure** — reject fast under overload rather than queueing unboundedly.
7. **Budgets and per-user quotas**, with a decided hard-stop behaviour.
8. **Attribution tags** on every request, and a report answering "where did the money go."
9. **A forecast** with trajectory alerting.
10. `make check` green.

### The exercises

**1 · Profile before optimising.** From your traces: cost by route, the input/output split, cache
rates, and the p99 tail. **Read ten traces from the expensive 1%.** Write down the pattern.

**2 · Semantic cache calibration.** Run it at thresholds from 0.90 to 0.99. For each, measure hit
rate *and* **false-hit rate** — hits where the cached answer was wrong for the new question.
Plot both. Choose, and justify.

**3 · Route evaluation.** Run your full eval suite on each route separately. **Find the route
where the cheap model underperforms** and decide whether to fix the routing or the model choice.

**4 · The latency waterfall.** Decompose one request end to end. Cut 30%. Say which stage and
what it cost you.

**5 · Load test.** Ramp concurrent requests until something breaks. Find your actual capacity.
Then add backpressure and confirm it degrades cleanly instead of collapsing.

**6 · Degradation drill.** Kill the reranker. Kill the vector store. Rate-limit the model. For
each: does the system degrade or fail? Is the degradation recorded?

**7 · Cost attribution report.** Produce a report a non-engineer could read: spend by feature, by
team, trend, and forecast. **This is the artefact that gets an AI project renewed.**

---

## 25.8 · Checkpoint

> **Move on to Chapter 26 when all of these are true.**

**Explain, out loud:**

1. Why you profile from traces rather than estimate, and what the p99 tail usually contains.
2. The four cache layers and what each catches that the others don't.
3. Why a semantic cache threshold that's too loose is a correctness bug, not a caching bug.
4. Why a per-route eval score is what makes routing defensible.
5. Why lower effort is usually tried before a cheaper model.
6. Why rejecting fast beats queueing under overload.
7. Why "sources without a generated answer" is a legitimate degradation tier.
8. The difference between cost optimisation and cost governance.

**Verify:**

9. Four cache layers, with hit rates visible.
10. A calibrated semantic threshold with a measured false-hit rate.
11. A per-route eval table.
12. A measured latency waterfall, with 30% cut from somewhere.
13. Degradation tested by killing each dependency in turn.
14. Budgets, quotas and a forecast, with a decided hard-stop behaviour.

---

## 25.9 · Going deeper (optional)

**Read about prefill versus decode.** Input processing is parallel; output generation is
sequential. That single fact explains the whole shape of LLM latency and tells you which lever
moves TTFT versus total time.

**Read engineering blog posts on LLM cost at scale.** The good ones always lead with a measured
baseline and a profile. Note how rarely the biggest win is the clever technique.

**If you want the queueing theory:** read about Little's Law and backpressure. The maths behind
"why does everything collapse at 80% utilisation" is worth an hour and applies far beyond this
domain.

---

<div align="center">

**[← Chapter 24](../ch24-security/)** · **[The Book](../../readme.md)** · **[Chapter 26 → Deployment](../ch26-deployment/)**

*Chapter 25 of 31 · Week 25*

</div>
