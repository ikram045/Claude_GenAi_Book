# Chapter 23 · Observability & Tracing

### Debugging a system that can't be reproduced

> **Week 23 · ~22 hours · Infrastructure and instrumentation**
>
> You cannot attach a debugger to a probabilistic system. Traces are what you get instead —
> and they're better than they sound, because they also become your eval cases.

---

## 23.0 · Why this chapter exists

A user says: *"It told me the wrong refund window yesterday."*

In a deterministic system you reproduce it: same input, same output, step through, find the bad
line. Here, you run the same question and get a *different, correct* answer. The bug is real and
it has vanished.

So the only way to understand what happened is to **have recorded it while it happened.** Not
logs — a full trace of the specific request: what was retrieved, what prompt was assembled, what
the model returned, what it cost, how long each stage took.

Chapter 1's Tuesday began with exactly this, and it was resolved in thirty minutes because the
trace existed. Without it, that bug is unfixable — you'd be guessing at a system you cannot
reproduce.

There's a second reason, and it's the one that compounds:

> **Every production failure, captured in a trace, becomes an eval case.**
>
> Chapter 22 gave you a test suite. This chapter is how it grows on its own, forever, from real
> failures instead of imagined ones.

That loop is the most valuable thing in Part V.

---

## 23.1 · Why this is different from normal observability

You know observability. Latency, error rates, throughput, dashboards. Most of it transfers.
Three things don't.

**1 · Success isn't binary.** HTTP 200 with a hallucinated answer is a failure that every
conventional metric records as a success. Your error rate can be 0.01% while your system is
badly wrong.

**2 · There's no stack trace.** When output is wrong, there's no line number. The "why" lives in
what went *into* the model — the retrieved chunks, the assembled prompt, the conversation
history. If you didn't record those, the cause is gone.

**3 · Re-running doesn't reproduce.** The single most important debugging technique you have is
unavailable. Recording replaces reproduction.

| | Conventional | LLM system |
|---|---|---|
| Failure signal | Exception, 5xx | Often none |
| Root cause | Stack trace | The assembled prompt |
| Reproduction | Re-run it | Impossible — record instead |
| "Working" | No errors | A distribution you track |
| Primary artefact | Logs and metrics | **Traces** |

---

## 23.2 · What a trace is

A tree of timed **spans** covering one request.

```
▼ request  req_7a3f  ·  2.84s  ·  $0.0127
  ├─ ▼ query_understanding          180ms   $0.0004
  │    └─ rewrite  "what about standard?" → "refund window for standard customers"
  ├─ ▼ retrieval                    310ms
  │    ├─ vector_search      top 50   ·  42ms
  │    ├─ bm25_search        top 50   ·  18ms
  │    ├─ rrf_fusion         50 → 50  ·   2ms
  │    └─ rerank             50 → 5   · 248ms
  ├─ ▼ consolidation                  4ms
  │    └─ 5 chunks · 2 deduped · 3,140 tokens · reordered
  ├─ ▼ generation                  2.31s   $0.0123
  │    ├─ prompt_assembled   4,210 in · cache_read 3,100
  │    ├─ ttft                       410ms
  │    └─ response           380 out · stop_reason end_turn
  └─ ▼ verification                  12ms
       └─ citations [1][3] valid · grounding_check passed
```

Every question you'd want to ask is answerable from that: what was retrieved, whether the right
chunk survived consolidation, whether the cache hit, where the time went, what it cost.

**The span tree maps to your pipeline.** If you built it in chapters 11–17, you already know the
structure.

---

## 23.3 · What to record

The complete list. Each item exists because you will one day need it.

### The request
```
request_id · session_id · user_id (or a pseudonymous id) · timestamp
route · input · conversation turn number
```

### Retrieval — everything
```
original query · rewritten query
per retriever: top-k ids, scores, latency
fused ranking · reranked ranking with scores
chunks that survived consolidation
chunks DROPPED, and why  ← this is how you diagnose RAG failure mode 4
```

### The model call — everything
```
model · the EXACT assembled prompt  ← non-negotiable
system prompt version · prompt template version
temperature / effort / max_tokens
input_tokens · output_tokens · cache_read · cache_creation
ttft · total latency · stop_reason · cost
the raw response, all content blocks
```

> **Log the exact assembled prompt.** Not the template — the rendered string with every variable
> interpolated. Section 15.5 says three of the eight RAG failure modes are only diagnosable from
> it, and roughly a third of "the model is being stupid" turns out to be an empty variable or a
> broken f-string. If you record one thing, record this.

### Tools and agents
```
per call: tool name, arguments, result size, duration, error status
per iteration: which guard was evaluated, which fired
approval requests and their outcomes
the whole loop: iterations, total cost, termination reason
```

### Verification and outcome
```
citation validity · grounding checks · refusal detected
user feedback, when it arrives
```

### The shape

```python
@dataclass
class Span:
    span_id: str
    parent_id: str | None
    trace_id: str
    name: str
    started_at: float
    duration_ms: float
    attributes: dict[str, Any]
    status: Literal["ok", "error"]
    error: str | None = None
```

Standard OpenTelemetry shape. Use it — the tooling ecosystem is real and you get it free.

---

## 23.4 · Tooling

Three layers, and you want all three.

**Traces** — the request tree. Your primary debugging artefact.
**Metrics** — aggregates over time. Your primary alerting signal.
**Logs** — narrative detail. Useful, secondary.

### What to use

| Option | Good for |
|---|---|
| **OpenTelemetry + your existing backend** | You already have observability; LLM spans are just spans |
| **LLM-specific platforms** (Langfuse, LangSmith, Phoenix and others) | Prompt/response viewers, cost dashboards, eval integration, built for this shape |
| **Your own** | Full control, no vendor, more work |

**Instrument with OpenTelemetry regardless.** It's a standard, it's vendor-neutral, and you can
point it at anything. Then add an LLM-specific platform if you want the purpose-built UI — most
of them ingest OTel.

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def answer(question: str, ctx: RequestContext) -> Answer:
    with tracer.start_as_current_span("rag.answer") as span:
        span.set_attribute("request.id", ctx.request_id)
        span.set_attribute("input.question", question)

        with tracer.start_as_current_span("rag.retrieve") as rspan:
            results = await retrieve(question)
            rspan.set_attribute("retrieval.count", len(results))
            rspan.set_attribute("retrieval.top_score", results[0].score if results else 0)
            rspan.set_attribute("retrieval.chunk_ids", [r.chunk.id for r in results])

        with tracer.start_as_current_span("rag.generate") as gspan:
            prompt = assemble(question, results)
            gspan.set_attribute("llm.prompt", prompt)          # ← the important one
            gspan.set_attribute("llm.model", MODEL)

            response = await call_model(prompt)

            gspan.set_attribute("llm.input_tokens", response.usage.input_tokens)
            gspan.set_attribute("llm.output_tokens", response.usage.output_tokens)
            gspan.set_attribute("llm.cache_read", response.usage.cache_read_input_tokens)
            gspan.set_attribute("llm.stop_reason", response.stop_reason)
            gspan.set_attribute("llm.cost_usd", cost_of(response.usage))

        return build_answer(response, results)
```

**One rule: instrument once, at the boundaries of your pipeline stages.** Not inside every
function — you'll drown in spans and pay for the storage. The stage boundaries you designed in
Part III are exactly the right granularity.

---

## 23.5 · Correlation

A user complains. You need to get from their sentence to the trace in under a minute.

**Return the request ID to the client.** In a header, and — for AI products — often in the UI
itself:

```python
response.headers["X-Request-ID"] = ctx.request_id
```

Then *"it gave me the wrong answer in this conversation"* becomes a trace lookup rather than an
archaeology project.

**Propagate one ID everywhere.** Through retrieval, through the model call, through every tool,
through every subagent (section 20.6), and into your logs and metrics. One ID, one story.

**Index by what you'll search on:** request ID, session ID, user ID, route, time range, and —
this is the useful one — **outcome**. Being able to ask *"show me every request last week where
the model refused"* or *"where top retrieval score was under 0.4"* is how you find problems
before users report them.

---

## 23.6 · Metrics that matter

Standard service metrics plus a layer specific to this kind of system.

### Quality proxies

You cannot measure correctness in production — there's no answer key. But these correlate, and
they move when things break:

| Metric | Why it matters | Bad sign |
|---|---|---|
| **Refusal rate** | Retrieval health, corpus coverage | Rising sharply — or near zero |
| **Top retrieval score distribution** | Are we finding relevant material? | Distribution shifting down |
| **Citation validity rate** | Hallucinated citations | Any non-zero rate |
| **Grounding check pass rate** | Unsupported claims | Falling |
| **Empty retrieval rate** | Queries matching nothing | Rising |
| **User feedback rate** | Direct signal | Thumbs-down rising |
| **Regeneration rate** | Users asking again = dissatisfaction | Rising |
| **Conversation abandonment** | Left mid-task | Rising |

> **Refusal rate has two failure directions**, and this catches people out. Rising means
> retrieval is degrading or questions have drifted. **Near zero means the model isn't refusing
> when it should**, which is worse — it's answering things it shouldn't know.

### Cost and performance

```
cost per request · p50/p95/p99 · by route · by model
tokens in/out/cached per request
cache hit rate    ← section 9.4's silent failure. Alert on this.
TTFT p50/p95
total latency p50/p95/p99
agent iterations p50/p95, and rate hitting the cap
```

### Reliability

```
error rate by class (rate limit, timeout, refusal, tool failure)
retry rate · truncation rate (stop_reason == max_tokens)
guard trigger rate by guard
```

**Report percentiles, never means.** A 1.2s mean with a 14s p99 feels broken to one user in a
hundred, every day, and the mean will never tell you.

---

## 23.7 · Alerting on a probabilistic system

The hard part, because you can't alert on "the answer was wrong."

### Alert on distributions, not events

One refusal is normal. **Refusal rate doubling week over week** is a signal.

```python
ALERTS = [
    Alert("refusal_rate", above=0.15, window="1h",
          note="retrieval may be degrading, or the corpus has a gap"),
    Alert("refusal_rate", below=0.01, window="24h",
          note="model may not be refusing when it should"),
    Alert("cache_hit_rate", below=0.30, window="1h",
          note="something is invalidating the prefix — check for timestamps"),
    Alert("citation_validity", below=0.99, window="1h",
          note="hallucinated citations — investigate immediately"),
    Alert("cost_per_request", above=2.0, relative_to="7d_median",
          note="cost doubled — check context growth or an agent loop"),
    Alert("p95_latency", above=1.5, relative_to="7d_median"),
    Alert("agent_cap_rate", above=0.10, window="1h",
          note="10% of agent runs hitting the iteration cap"),
    Alert("empty_retrieval_rate", above=0.05, window="1h"),
]
```

**Comparing to a rolling baseline beats absolute thresholds**, because "normal" drifts as your
corpus and traffic change, and absolute thresholds either fire constantly or never.

### Budget alarms specifically

```python
if projected_monthly_spend() > settings.monthly_budget * 0.8:
    alert("80% of monthly LLM budget projected")
```

An agent loop or a caching regression can multiply your bill overnight. You want to hear about it
that night.

### Canary cases

The cheapest early-warning system there is: run 10 eval cases against production every fifteen
minutes and alert if the pass rate drops.

```python
async def canary() -> None:
    results = await run_eval_suite("canary", target="production")
    if results.pass_rate < 0.9:
        alert(f"canary at {results.pass_rate:.0%}", failures=results.failures)
```

This catches things no proxy metric will — a model version change, a corpus corruption, a config
drift. Ten cases, a few cents per run, and it tells you within fifteen minutes.

---

## 23.8 · The flywheel

**The most valuable thing in this chapter.** Traces and evals feed each other.

```
     production
         │
    ┌────▼────┐
    │  TRACE  │  every request recorded
    └────┬────┘
         │  a failure is noticed — complaint, metric, review
    ┌────▼────┐
    │ TRIAGE  │  read the trace, categorise (Ch 15 / Ch 17 failure modes)
    └────┬────┘
         │
    ┌────▼────┐
    │  CASE   │  add it to the eval suite, with its expected behaviour
    └────┬────┘
         │
    ┌────▼────┐
    │   FIX   │  change something; eval proves it works
    └────┬────┘
         │
    ┌────▼────┐
    │   CI    │  the case now guards against regression, forever
    └────┬────┘
         │
     production
```

The properties of this loop are what make it worth building:

- **Your eval suite grows from real failures**, not imagined ones. Real failures are always more
  surprising and more valuable than anything you'd invent.
- **Every bug fixed once stays fixed.** The case is in CI.
- **Your suite becomes a map of how your system actually fails**, categorised.

```python
async def trace_to_eval_case(trace_id: str, expected: str, tags: list[str]) -> EvalCase:
    trace = await traces.get(trace_id)
    return EvalCase(
        id=f"prod-{trace_id[:8]}",
        input={"question": trace.input.question,
               "conversation": trace.input.conversation},
        expected={"behaviour": expected},
        checks=[...],
        tags=[*tags, "from-production"],
        notes=f"Reported {trace.timestamp:%Y-%m-%d}. Original failure: {trace.diagnosis}",
    )
```

**Make this one command.** If converting a trace into an eval case takes five minutes of manual
work, it won't happen. If it takes ten seconds, your suite grows every week.

### Collect user feedback

```python
@app.post("/feedback")
async def feedback(request_id: str, rating: Literal["up", "down"], comment: str | None):
    await feedback_store.record(request_id, rating, comment)
    if rating == "down":
        await triage_queue.add(request_id)       # ← goes straight into the loop
```

A thumbs-down attached to a request ID is a trace you should read, and often an eval case you
should add. **Review the queue weekly.** This is the cheapest quality process available and
almost nobody runs it.

---

## 23.9 · Privacy

Traces contain everything — user questions, retrieved documents, generated answers. That's what
makes them useful and what makes them a liability.

**Redact before storage.** Credentials, keys, card numbers, and PII where you can detect it.
Run redaction at the recording boundary, not at display time.

**Set retention.** Full traces for 7–30 days; aggregated metrics indefinitely. Storage is cheap
but liability isn't, and old traces are rarely useful.

**Control access.** Traces are production data with production sensitivity. Log who reads them.

**Support deletion.** If a user's data must be deleted, it has to come out of your traces too —
the same problem as section 18.6's memory deletion, with the same compliance dimension.

**Be careful with samples.** It's tempting to keep a "interesting examples" folder. That folder
is production data with none of the controls.

> **If you'd be uncomfortable with a user seeing their own trace, you're storing too much.**
> That's a good working test.

---

## 23.10 · Build it

**An observability layer** across everything you've built.

```
src/genai_toolkit/observability/
├── tracing.py     OTel setup, span helpers for each pipeline stage
├── attributes.py  standard attribute names, so spans are queryable
├── redact.py      PII and secret redaction at the boundary
├── metrics.py     the section 23.6 metric set
├── alerts.py      rolling-baseline alerting
├── canary.py      periodic eval against production
├── feedback.py    collection and triage queue
└── to_eval.py     trace → eval case, one command
```

Requirements:

1. **Full tracing** across retrieval, generation, tools and agent loops, as a span tree.
2. **The exact assembled prompt** recorded on every model call.
3. **Chunks dropped in consolidation** recorded, with the reason.
4. **One request ID** propagated everywhere, returned to the client.
5. **Redaction** at the recording boundary, tested.
6. **All the metrics from 23.6**, with percentiles.
7. **Rolling-baseline alerts**, including both refusal-rate directions and cache hit rate.
8. **A canary** running 10 eval cases against production on a schedule.
9. **A trace viewer** — even a plain terminal renderer. You must be able to read a trace.
10. **`trace-to-eval` as one command.**
11. **Feedback collection** feeding a triage queue.
12. `make check` green.

### The exercises that matter

**1 · Debug from a trace alone.** Have someone (or a script) introduce a bug in your pipeline.
Find it using only traces — no re-running, no print statements. **This is the skill.**

**2 · Run the flywheel once, end to end.** Find a real failure in your own usage. Read the trace.
Categorise it. Convert it to an eval case. Fix it. Watch CI go green. **Time the whole loop.** If
it took more than an hour, find the slow step and automate it.

**3 · Break your cache and watch the alert fire.** Add a timestamp to your system prompt. Confirm
the cache-hit-rate alert catches it within the window. **This is section 9.4's silent failure,
made loud.**

**4 · Prove the canary works.** Point it at a deliberately broken config. Confirm it alerts.

**5 · Redaction test.** Push a synthetic credit card number and an API key through your pipeline.
Search your stored traces for them. **They must not be there.**

**6 · Tail latency investigation.** Find your slowest 1% of requests. Read ten traces. What do
they have in common? Fix it. Measure p99 before and after.

---

## 23.11 · Exercises

**1 · Span granularity.** Instrument at three levels — coarse, medium, fine. Measure the storage
cost and the debugging usefulness of each. Find your level.

**2 · Attribute schema.** Define a standard set of attribute names across your whole system. Then
write three queries you couldn't answer without them.

**3 · The outcome index.** Make traces searchable by outcome — refused, low retrieval score,
truncated, guard triggered. Use it to find a problem before any user reports it.

**4 · Alert tuning.** Set an absolute threshold and a rolling-baseline one for the same metric.
Run for a week. **Count false positives for each.** Report which you'd keep.

**5 · Feedback correlation.** Collect thumbs-up/down for 100 requests. Correlate against your
proxy metrics. **Which proxy actually predicts dissatisfaction?** That's the one to alert on.

**6 · Trace-derived eval suite.** Build 20 eval cases entirely from production traces. Compare
them to your hand-written cases — which are harder? Which are more surprising?

**7 · Cost attribution.** From traces alone, produce: cost by route, by user, by tag, by hour.
Find your most expensive 1% of requests and explain what they have in common.

**8 · A one-page trace.** Design a terminal rendering that fits one screen and answers the five
questions you ask most often. Use it for a week. Iterate.

---

## 23.12 · Checkpoint

> **Move on to Chapter 24 when all of these are true.**

**Explain, out loud:**

1. Three reasons observability for LLM systems differs from conventional observability.
2. Why recording replaces reproduction, and what that implies about what you record.
3. Why the exact assembled prompt is the single most important thing to log.
4. Why refusal rate has two failure directions.
5. Why you alert on distributions rather than events, and on rolling baselines rather than
   absolute thresholds.
6. The flywheel, and why it makes your eval suite better than one you could design.
7. Why traces are a privacy liability and what to do about it.

**Write from memory:**

8. A span tree covering retrieval → generation → verification with the right attributes.
9. A rolling-baseline alert definition.
10. A canary that runs eval cases against production.
11. `trace_to_eval_case`.

**Verify:**

12. You have debugged a real bug using only a trace.
13. You have run the full flywheel — production failure to CI-guarded eval case — at least once.
14. Your cache-hit alert fires when you deliberately break caching.
15. Redaction is tested: a synthetic secret does not appear in stored traces.
16. `trace-to-eval` is one command.

Number 13 is the one. **The flywheel is the mechanism that makes your system get better over
time instead of drifting**, and having run it once means you'll keep running it.

---

## 23.13 · Going deeper (optional)

**Read the OpenTelemetry semantic conventions for generative AI.** There's a developing standard
for LLM span attributes. Following it means your traces work with tools you haven't chosen yet.

**Try one LLM-specific platform** on a real project for a week. The purpose-built prompt/response
viewers and eval integration are genuinely better than a generic tracing UI for this workload.
Decide for yourself whether that's worth the dependency.

**If you want the general theory:** read about observability versus monitoring — the distinction
between "is it up" and "can I ask arbitrary questions about what happened." LLM systems need the
second kind badly, because the questions you'll need to ask are ones you didn't anticipate.

**If you want the practical angle:** find a post-mortem of an AI product incident. Note how much
of the investigation depended on having recorded the right thing, and how much on having recorded
it *before* anyone knew it mattered.

---

<div align="center">

**[← Chapter 22](../ch22-evals/)** · **[The Book](../../readme.md)** · **[Chapter 24 → Security](../ch24-security/)**

*Chapter 23 of 31 · Week 23*

</div>
