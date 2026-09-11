# Chapter 9 · Context, Cost & Latency

### Thinking in tokens, and the difference between a $3,000 bill and a $560 one

> **Week 8, part 2 · ~11 hours · Measurement and arithmetic**
>
> The chapter that makes you commercially credible. Anyone can build an AI feature. Being
> able to say what it costs, why, and how to make it cheaper without making it worse is a
> different level of engineer.

---

## 9.0 · Why this chapter exists

Every AI feature has three properties that a demo hides completely:

**What it costs.** Per request, per user, per month, at scale.
**How long it takes.** And specifically, how long before the user sees *anything*.
**How much context it needs.** Which drives both of the above.

Get these wrong and you build something that works beautifully in development and is
commercially impossible in production. This happens constantly. A team ships an AI feature,
usage grows, and three months later someone in finance asks why the API bill is larger than
the engineering team's salaries.

The skill here is not frugality. It's **knowing where the money goes and making deliberate
tradeoffs.** By the end of this chapter you'll take a realistic system from $3,150/month to
$558/month with no quality loss — and, more importantly, you'll be able to explain each step
and what it cost you.

That explanation is an interview answer. Very few candidates have one.

---

## 9.1 · Thinking in tokens

Tokens are the unit of everything here: cost, latency, and context limits are all denominated
in them. Internalise these:

```
1 token          ≈ 4 characters  ≈ 0.75 English words
1,000 tokens     ≈ 750 words     ≈ 1.5 pages
100,000 tokens   ≈ 75,000 words  ≈ a short novel
```

And the conversions you'll actually reach for:

| Content | Rough tokens |
|---|---|
| A tweet | 30–70 |
| An email | 200–500 |
| A page of prose | 500–700 |
| A 10-page PDF | 5,000–7,000 |
| A 300-page book | 120,000–180,000 |
| A medium source file | 1,000–3,000 |
| A typical RAG context (5 chunks) | 2,000–5,000 |

**Two multipliers that will surprise you:**

**Code costs more than prose.** Punctuation, indentation and identifiers fragment badly. The
same "amount of information" in code can run 1.5–2× the tokens of English text.

**Non-English costs much more.** Two to four times, for the reason in section 5.2 — the
tokenizer has fewer whole-word tokens for those scripts. If you serve a multilingual audience,
model your costs per language or you will be badly wrong.

For anything that matters, measure rather than estimate:

```python
count = client.messages.count_tokens(model="claude-opus-5", system=sys, messages=msgs)
```

---

## 9.2 · The cost model

You are billed per token, separately for input and output, at rates that differ by model. A
current snapshot:

| Model | Input $/1M | Output $/1M | Output multiple |
|---|---:|---:|:---:|
| Claude Opus 5 | $5.00 | $25.00 | 5× |
| Claude Sonnet 5 | $2.00 | $10.00 | 5× |
| Claude Haiku 4.5 | $1.00 | $5.00 | 5× |

**Output costs roughly five times input.** Remember that ratio — it determines which lever to
pull first for any given workload.

Then there are two modified rates, and they are where the real money is:

| Token type | Multiplier | Effective rate on Opus 5 |
|---|:---:|---:|
| Normal input | 1.0× | $5.00 /1M |
| **Cache write** | ~1.25× | $6.25 /1M |
| **Cache read** | **~0.1×** | **$0.50 /1M** |

> **A cached input token costs exactly one tenth of a fresh one.** That single number is the
> most important fact in this chapter. Everything in section 9.4 is about making as much of
> your input as possible qualify for it.

### Costing a single request

```python
INPUT_PER_MTOK  = 5.00
OUTPUT_PER_MTOK = 25.00

def request_cost(usage) -> float:
    return (
        usage.input_tokens                  * INPUT_PER_MTOK
        + usage.cache_read_input_tokens     * INPUT_PER_MTOK * 0.10
        + usage.cache_creation_input_tokens * INPUT_PER_MTOK * 1.25
        + usage.output_tokens               * OUTPUT_PER_MTOK
    ) / 1_000_000
```

Log this on every request. You built the ledger in Chapter 6's exercises; this is what fills
it.

### Scaling it up

A single request costing $0.05 feels free. Multiply:

```
$0.05 × 100 requests/day        = $5/day        = $150/month
$0.05 × 10,000 requests/day     = $500/day      = $15,000/month
$0.05 × 100,000 requests/day    = $5,000/day    = $150,000/month
```

**Always compute the monthly figure at your target scale, early.** Not because you'll hit it
tomorrow, but because $150,000/month is a business-model problem, not an engineering problem,
and it's much cheaper to discover in week 8 than in month nine.

---

## 9.3 · Where the money actually goes

Before optimising, find out what you're paying for. The answer is usually not what people
guess.

Take a realistic support assistant:

```
System prompt + few-shot examples     4,000 tokens   (identical every request)
Retrieved context (RAG, top-10)       6,000 tokens   (varies)
User question                           100 tokens   (varies)
Answer                                  500 tokens   (generated)

50,000 requests/month, on Opus 5
```

The bill:

```
Input:   10,100 × 50,000 = 505M tokens × $5.00/1M  = $2,525
Output:     500 × 50,000 =  25M tokens × $25.00/1M =   $625
                                              TOTAL = $3,150/month
```

Look at that breakdown. **80% of the cost is input.** Not the clever generation you're proud
of — the context you shovel in before it.

This is the normal shape for a RAG system, and it's why beginners optimise the wrong thing.
They shorten the answer (20% of cost) and leave 4,000 tokens of unchanging system prompt being
repurchased at full price fifty thousand times a month.

> **Rule: profile before you optimise.** The same rule as any other performance work, and
> ignored just as often.

---

## 9.4 · Prompt caching

The single highest-value optimisation available, and it costs you no quality at all.

### How it works

Mark a portion of your prompt as cacheable. The provider stores the processed state of that
prefix. On the next request with an identical prefix, that work is reused and you pay ~10%.

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    system=[{
        "type": "text",
        "text": LARGE_STABLE_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }],
    messages=[{"role": "user", "content": question}],
)
```

Or the simpler top-level form, which caches the last cacheable block automatically:

```python
cache_control={"type": "ephemeral"}
```

### The one rule that governs everything

**Caching is a prefix match.** The cache hits only if everything from the very start of the
request up to your cache marker is **byte-identical** to the previous request.

The render order is fixed:

```
    tools  →  system  →  messages
    └──────────────────────┬──────────────────────┘
       everything before your marker must be identical
```

Therefore: **stable content first, volatile content last.**

```
┌──────────────────────────────┐
│ tools (sorted, deterministic)│  ← stable
│ system prompt                │  ← stable
│ few-shot examples            │  ← stable
├──────────────────────────────┤  ← cache marker here
│ retrieved documents          │  ← varies
│ conversation history         │  ← varies
│ the user's question          │  ← varies, and goes LAST (section 7.2)
└──────────────────────────────┘
```

### The silent invalidators

These destroy every cache hit after them, produce no error, and are invisible unless you
check. Each of these has cost someone real money:

| Invalidator | Fix |
|---|---|
| `datetime.now()` in the system prompt | Move it after the cache marker, or drop it |
| A request ID or UUID in the prefix | Same |
| `json.dumps(d)` on an unordered dict | `json.dumps(d, sort_keys=True)` |
| Tool list built from a `set` | Sort it — iteration order must be deterministic |
| A/B testing prompt variants | Each variant is its own cache namespace; expect lower hit rates |
| Switching models mid-conversation | **Caches are model-scoped.** A model cascade forfeits reuse |
| Changing `effort` mid-conversation | Invalidates the messages cache on most models |

### Always verify

```python
print(response.usage.cache_read_input_tokens)
```

> **If this is zero across repeated requests with the same prefix, caching is not working.**
> People have run for months believing they had caching on, paying full price the entire time,
> because nobody ever printed this number. Put it in your ledger and put it on a dashboard.

### The practical details

- Default cache lifetime is about **5 minutes**, refreshed on each hit. A longer TTL is
  available at higher write cost — worth it for a document queried steadily all day.
- There's a **minimum cacheable prefix** (roughly 512–4,096 tokens, model-dependent). Below
  it, nothing caches and you get no warning.
- At most **4 cache breakpoints** per request.
- A cache write costs ~1.25×, so caching something used only once is a small loss. Cache
  what's reused.

### What it's worth

Apply caching to the 4,000-token stable prefix in our example:

```
Cache reads:  4,000 × 50,000 = 200M × $0.50/1M  =   $100
Cache writes: occasional refresh                 =   ~$12
Uncached input: 6,100 × 50,000 = 305M × $5.00/1M = $1,525
Output:                                            $625
                                           TOTAL = $2,262/month
```

**$3,150 → $2,262. A 29% cut, zero quality change, about ten lines of code.**

Modest here because the stable prefix is only 40% of input. Now consider a document-QA system
where a **50,000-token document** is the stable prefix and questions are short:

```
Without caching:  $2,605/month
With caching:       $449/month      ← 5.8× cheaper
```

The larger and more stable your prefix, the more caching is worth. Systems where one big
document dominates are the best case in the entire field.

---

## 9.5 · The other free wins

Neither of these costs you any quality either. Do them before anything in section 9.6.

### Trim the context

Look again at the breakdown: 6,000 tokens of retrieved context per request, $1,525/month.

Most RAG systems retrieve far more than they need — top-10 chunks when the answer lives in
two. Adding a reranking step (Chapter 13) that cuts retrieval from 10 chunks to 3:

```
Uncached input: 3,100 × 50,000 = 155M × $5.00/1M = $775     (was $1,525)
                                           TOTAL = $1,512/month
```

**$2,262 → $1,512. Another 33%.**

And here is the part that surprises people: from section 5.11, *less context often produces
better answers.* Attention is diluted across long contexts, and irrelevant chunks are active
distractors. Better retrieval is simultaneously a cost win and a quality win. That's rare
enough to be worth remembering.

### Cache your own responses

Real traffic is repetitive. In most support and documentation systems, 10–20% of questions are
near-exact repeats of earlier ones.

```python
key = hashlib.sha256(f"{model}|{system}|{question}".encode()).hexdigest()
if cached := await redis.get(key):
    return cached
```

A response cache costs **nothing** on a hit — no tokens at all — and returns in milliseconds.
The tradeoff is staleness: invalidate when your corpus changes, and never cache anything
personalised.

---

## 9.6 · The levers that cost you something

Free wins first. Only then these — and each requires measurement, because each trades
something away.

### Lever 1 · Effort

From section 6.6: `effort` controls how much reasoning the model does. It's your **first**
quality-trading lever, ahead of model choice, for a reason worth understanding:

> **One model means one cache namespace.** Caches are model-scoped, so a multi-model cascade
> forfeits cache reuse across its models. Lowering effort keeps you on one model and keeps
> your cache intact.

Whether a workload repays higher effort is a property of the workload, not a universal:

| Workload | Typically |
|---|---|
| Coding, long-horizon agentic tasks | Respond strongly to higher effort |
| Chat, classification, high-volume routing | Often fine at `low` |
| Anything latency-sensitive | `low` or `medium` |

Measure on real requests before changing a default, and tune **per route**, not globally.

### Lever 2 · Model routing

Not every request needs your best model. Classify, then route.

In our example, suppose 60% of queries are straightforward lookups that a smaller model
handles well:

```
30,000 requests → Haiku 4.5  ($1 / $5)     = $182
20,000 requests → Opus 5     ($5 / $25)    = $605
                                     TOTAL = $786/month
```

**$1,512 → $786. Another 48%.**

Three caveats that people learn the hard way:

1. **You must measure quality per route.** Run your eval suite on the cheap route
   specifically. A router that quietly degrades 60% of your answers is not a saving.
2. **The router itself costs something.** A small classification call adds tokens and latency
   to every request. Sometimes a keyword heuristic does the job for free.
3. **Try lower effort on the better model first.** On newer models, lower effort frequently
   matches or beats a previous-generation model at high effort — and you keep one cache
   namespace. Measure both before committing to a cascade.

### Lever 3 · Shorter outputs

Output is 5× the price of input, so output length is disproportionately expensive.

```
Answer: 500 tokens → 300 tokens
Haiku: $45, Opus: $150  (was $75 / $250)
                 TOTAL = $656/month
```

**$786 → $656.**

You achieve this in the prompt: *"Maximum 3 sentences."* Chapter 7's specificity, showing up
on your invoice. Don't cap it with `max_tokens` — that truncates mid-sentence and costs you a
retry.

### Lever 4 · Batch processing

For anything not latency-sensitive — nightly summarisation, corpus embedding, backfills,
eval runs — the Batch API processes asynchronously at roughly **half price**.

If a slice of your workload can wait, this is a 50% cut on that slice for one line of code.
Remember it in Chapter 11 when you embed a whole corpus.

---

## 9.7 · The ladder, assembled

| Step | Change | Monthly | Total saving | Quality cost |
|:---:|---|---:|:---:|---|
| 0 | Baseline (Opus 5, no caching) | $3,150 | — | — |
| 1 | Prompt caching | $2,262 | 1.4× | **None** |
| 2 | Rerank, context 6k → 3k | $1,512 | 2.1× | **None — improves** |
| 3 | Route 60% to Haiku | $786 | 4.0× | Measured, small |
| 4 | Cap outputs at 300 tokens | $656 | 4.8× | Measured, small |
| 5 | Response cache (15% exact repeats) | $558 | **5.6×** | Staleness risk |

**$3,150 → $558.** The first two steps are free and account for over half the saving.

> **The lesson is the order.** Beginners start at step 3 — "let's use a cheaper model" — which
> is the first step that costs quality, and skip the two that don't. Do the free wins first,
> always. Then trade, deliberately, with measurement.

### Judge cost per completed task, not per request

A critical correction to all of the above: a cheaper request that needs two retries, or that
sends the user back to ask again, **is not cheaper.**

```
Route A: $0.05/request, works first time            → $0.05 per completed task
Route B: $0.01/request, 40% need a follow-up turn   → $0.014 per task... plus
                                                       an unhappy user
```

In agentic systems this effect dominates: a weaker model takes more turns to finish, and more
turns means more tokens. **Measure the task, not the call.**

---

## 9.8 · Latency

Cost is one axis. Users feel the other one.

### The metric that matters

**Time to first token (TTFT)** — how long before *anything* appears.

| | Non-streaming | Streaming |
|---|---|---|
| First visible text | 8s | 0.4s |
| Total time | 8s | 8s |
| Feels like | Broken | Fast |

Total time is identical. Perceived speed differs enormously. This is Chapter 4's lesson, and
it's worth repeating because it is the highest-leverage latency work you will ever do: **just
stream.**

### What actually drives latency

```
    ┌─ network round trip           ~50–200ms
    │
    ├─ input processing             grows with prompt length (attention is n²)
    │
    ├─ reasoning tokens             grows with effort — often the largest term
    │
    ├─ FIRST TOKEN                  ◄── TTFT lands here
    │
    └─ output generation            roughly linear in output length
```

Which gives you the levers, in order of usual impact:

| Lever | Effect on TTFT | Effect on total |
|---|---|---|
| **Stream** | Enormous (perceived) | None |
| **Lower effort** | Large | Large |
| **Shorter prompt** | Moderate | Moderate |
| **Prompt caching** | Moderate — cached prefix isn't reprocessed | Moderate |
| **Smaller model** | Moderate | Large |
| **Shorter output** | None | Large |
| **Parallelise steps** | Depends | Large in chains |

Note that **prompt caching helps latency as well as cost** — the cached prefix doesn't need
reprocessing. It's the rare optimisation that improves both axes and quality-neutral. Do it
first, for both reasons.

### Measure percentiles, not averages

```python
import time

start = time.perf_counter()
ttft = None

async with client.messages.stream(...) as stream:
    async for text in stream.text_stream:
        if ttft is None:
            ttft = time.perf_counter() - start
        yield text

total = time.perf_counter() - start
```

Log both, and report **p50, p95 and p99** — never the mean. The mean hides the tail, and the
tail is what users complain about. A system with a 1.2s average and a 14s p99 feels broken to
one user in a hundred, every single day.

---

## 9.9 · Context budgeting

Every request has a token budget. Spend it deliberately.

```python
CONTEXT_LIMIT = 200_000        # check your model's actual limit

budget = {
    "system_prompt":     4_000,     # fixed
    "few_shot":          2_000,     # fixed
    "retrieved_context": 6_000,     # ← the flexible one
    "conversation":      4_000,     # trimmed to fit
    "question":            500,
    "response":         16_000,     # max_tokens
}
```

When you exceed the budget, you have four options, in rough order of preference:

1. **Retrieve less.** Usually the right answer, and often improves quality (section 9.5).
2. **Summarise older conversation turns.** Chapter 18.
3. **Drop the oldest turns entirely.** Cheap, lossy, often fine.
4. **Use a longer-context model.** Expensive and slower — a last resort, not a first one.

> **Reminder from section 5.11:** a bigger context window is not automatically better. It
> costs more, runs slower, dilutes attention, and buries material in the middle where recall
> is worst. Retrieving the right 2,000 tokens beats supplying 200,000 and hoping. **Retrieval
> is a quality technique, not just a cost one.**

---

## 9.10 · Build it

**A cost and latency observatory.** Extend your Chapter 3 project:

```
src/genai_toolkit/metering/
├── pricing.py      per-model rates, and cost from a usage object
├── ledger.py       append-only JSONL: every request, every field
├── budget.py       context budgeting, with pre-flight token counting
└── report.py       aggregate and print
```

Requirements:

1. **Every request logged** to JSONL: timestamp, model, route, input/output/cache-read/
   cache-write tokens, cost, TTFT, total latency, `stop_reason`, success.
2. **A pre-flight check** using `count_tokens` that refuses a request exceeding the budget
   *before* you pay for it.
3. **A report command** printing: total spend, spend by model, spend by route, p50/p95/p99
   latency, **cache hit rate**, and cost per completed task.
4. **A cache-health warning** — flag any route whose `cache_read_input_tokens` is zero across
   more than N requests. This is the check that catches silent invalidation.
5. **A budget alarm** — log a warning when projected monthly spend crosses a configured
   threshold.
6. Tested against a fake client with synthetic usage objects. No API calls in CI.

### The real exercise

**Take one of your own workloads down the ladder, measuring at each step.** Produce a table
exactly like section 9.7's, with *your* numbers. Record what each step cost you in quality.

That table is a portfolio artefact. It is also, almost verbatim, the answer to one of the most
common senior-level interview questions in this field.

### Break it deliberately

1. Cache a large prefix, verify `cache_read_input_tokens` is non-zero, then insert
   `datetime.now()` into the system prompt. Watch it drop to zero and the cost triple.
   **Do this one — it makes the prefix rule permanent.**
2. Cache a prefix below the minimum cacheable size. Note that nothing caches and nothing warns
   you.
3. Put your cache marker *after* the volatile content instead of before. Observe the hit rate
   collapse.
4. Run the same prompt at every effort level. Record cost, TTFT and quality for each. Find the
   knee in the curve.
5. Compare average latency to p99 over 200 requests. Note how different they are.

---

## 9.11 · Exercises

**1 · Token census.** Take 100 real inputs from your domain. Measure the token distribution —
p50, p95, max. Do the same for outputs. **You cannot budget what you haven't measured.**

**2 · The multilingual surcharge.** Take one paragraph and translate it into four languages.
Measure tokens for each. Compute the per-language cost of 10,000 requests. Write down what you
think the fairness implication is.

**3 · Caching ROI.** For a workload of your choosing, compute the break-even: how many requests
must share a prefix before caching (at 1.25× write, 0.1× read) pays for itself? Derive it, then
verify empirically.

**4 · Build a router.** Classify queries as simple or complex, route accordingly. Then **run
your eval suite on the cheap route alone.** Report the quality delta and the money saved. Decide
whether you'd ship it.

**5 · Effort sweep.** One task, five effort levels, 20 inputs each. Plot cost against quality.
Identify the point of diminishing returns.

**6 · Cost per completed task.** Build something multi-turn. Measure cost per *resolved
request*, not per API call. Then try a cheaper model and see whether the extra turns eat the
saving. *(They often do. This is the most instructive exercise here.)*

**7 · Latency budget.** Decompose one request end to end: network, input processing, reasoning,
generation. Attribute milliseconds to each. Then cut total latency by 40% and say which lever
did it.

**8 · Project the bill.** Take your Project B assistant. Project monthly cost at 100, 10,000
and 1,000,000 requests per day. **At which scale does it stop being viable, and what would you
change first?**

---

## 9.12 · Checkpoint

> **Move on to Project B when all of these are true.**

**Compute, without looking anything up:**

1. Tokens in a 10-page document, and the cost of sending it 1,000 times.
2. Monthly cost of 50,000 requests at 8,000 input and 500 output tokens.
3. The saving from caching a 4,000-token prefix across those requests.
4. How much cheaper a cached input token is than a fresh one. *(Exactly 10×.)*

**Explain, out loud:**

5. Why input usually dominates cost in a RAG system.
6. What makes a cached prefix miss, and four ways to cause it accidentally.
7. Why lowering effort is usually a better first lever than switching models.
8. Why cost per completed task differs from cost per request, and when the gap matters most.
9. Why p99 latency matters more than the average.
10. Why retrieving *less* context can improve both cost and quality.

**Verify:**

11. Your ledger has 200+ real requests with full token and latency detail.
12. Your report shows cache hit rate, p95 latency, and spend by route.
13. You have taken a real workload down the ladder with a measured table.
14. You have broken your own cache with a timestamp and watched the cost triple.

---

## 9.13 · Going deeper (optional)

**Read the prompt caching documentation properly.** TTL options, breakpoint placement, and
the exact invalidation semantics. It's short and it's money.

**Read about the Batch API.** Half price for anything asynchronous. You'll use it in
Chapter 11.

**If you want the theory of the latency curve:** search for "inference latency" and
"prefill vs decode." Understanding that input processing (prefill) is parallel while output
generation (decode) is sequential explains the entire shape of the latency table in section
9.8 — and why output length dominates total time while prompt length dominates TTFT.

**If you want to see how professionals present this:** search for engineering blog posts about
LLM cost optimisation at scale. Note that the good ones always lead with a measured baseline,
never with a technique.

---

<div align="center">

**[← Chapter 8](../ch08-structured-output/)** · **[The Book](../../readme.md)** · **[Project B → Streaming Assistant](../project-b-streaming-assistant/)**

*Chapter 9 of 31 · Week 8 · End of Part II theory*

</div>
