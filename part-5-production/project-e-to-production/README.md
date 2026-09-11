# 🔨 Project E · To Production

### Week 26 · ~22 hours · **The one that gets you hired**

---

## The brief

Take **Project C or Project D** and make it something you'd be comfortable putting in front of
real users — with evals in CI, traces, a threat model, cost controls, a runbook, and a rollback
you've actually performed.

You are not building anything new this week. **You are making one existing system
trustworthy**, and then writing down what that took.

> **This is the single most valuable week in the book.**
>
> Almost every candidate for these roles has a demo. Some have an impressive one. Very few have
> a system with a CI gate that blocks quality regressions, a red-team suite that's green, a p99
> cost number, and a runbook they've followed. That gap is the entire difference between "I've
> used LLMs" and "I can be trusted with an LLM system in production."

---

## Which project to promote

**Choose the one you'd rather talk about for an hour**, because you will.

| | Project C (RAG) | Project D (Agent) |
|---|---|---|
| Easier to evaluate | ✓ Retrieval metrics are clean | Harder — success is end-state |
| Easier to make safe | ✓ Read-only | Harder — it acts |
| More impressive | Solid | ✓ More so, *if* the guardrails are real |
| Broader job relevance | ✓ RAG is in most postings | Growing fast |
| Best story | "Measured quality, improved it" | "Autonomy I can defend" |

**Recommendation: Project C**, unless your Project D genuinely excites you. RAG appears in more
job descriptions, its evaluation story is cleaner to present, and a well-measured retrieval system
is the most directly demanded artefact in the field.

**The strongest version:** promote Project C, and keep Project D as a separate repo that *uses*
it. "My agent queries my RAG service, which is deployed with evals in CI" is a coherent
two-project story that shows range.

---

## Requirements

Chapter 26's launch checklist is the specification. Grouped here by what it demonstrates.

### 1 · It's measured — Chapter 22

- [ ] Eval suite of **100+ cases**, reps ≥ 2, confidence intervals reported
- [ ] All four grader types where appropriate; atomic metrics, not one blended score
- [ ] **Judge calibrated against your own human labels, ≥ 90% agreement**, reported
- [ ] Oracle passes, null baseline fails — both as `make` targets
- [ ] Infra errors in a sidecar, never scored as model failures
- [ ] **Eval in CI, blocking merges on regression beyond your measured noise floor**
- [ ] Train/test split drawn at random; test touched rarely
- [ ] Noise floor computed and stated

### 2 · It's observable — Chapter 23

- [ ] Full traces: retrieval, generation, tools, with **the exact assembled prompt**
- [ ] Request ID returned to the client and propagated everywhere
- [ ] Metrics with percentiles; rolling-baseline alerts
- [ ] A canary running eval cases against production
- [ ] `trace-to-eval` as one command
- [ ] Feedback collection feeding a triage queue
- [ ] Redaction tested — a synthetic secret does not appear in stored traces

### 3 · It's safe — Chapter 24

- [ ] A written threat model and trifecta audit
- [ ] No tool takes an identity from its arguments
- [ ] Output filtering: domain allowlist, PII, markdown images
- [ ] Per-session rate and cost limits
- [ ] **A red-team suite running in CI, green**, with the attempt-vs-blocked numbers recorded

### 4 · It's affordable — Chapter 25

- [ ] Cost per request known, with p50/p95/p99
- [ ] Cache hit rates monitored and alerted on
- [ ] Budgets and per-user quotas, with a decided hard-stop behaviour
- [ ] A cost attribution report a non-engineer could read
- [ ] A latency waterfall, with one stage measurably improved

### 5 · It's operable — Chapter 26

- [ ] `docker compose up` from a clean clone
- [ ] Startup validation fails fast, including on a bad prompt version
- [ ] Liveness and readiness separated; `/health/live` responsive under load
- [ ] Runtime-selectable prompt versions; kill switches for every expensive feature
- [ ] Degradation chain tested by killing each dependency in turn
- [ ] **Rollback performed and timed**
- [ ] A runbook you have followed cold

---

## The week

| | Hours | Work |
|---|:---:|---|
| **Mon** | 3 | Grow the eval suite to 100+. Compute the noise floor. Calibrate the judge |
| **Tue** | 3 | Eval in CI with a gate. Break it on purpose and confirm it blocks |
| **Wed** | 3 | Tracing end to end. `trace-to-eval`. Canary. Redaction test |
| **Thu** | 3 | Threat model. Red-team suite. Fix what gets through. Put it in CI |
| **Fri** | 2 | Budgets, quotas, cost report, cache alerting |
| **Sat** | 5 | Deployment: compose, health, flags, degradation drills, rollback |
| **Sun** | 3 | Runbook, README, `PRODUCTION.md`, demo recording |

> **Monday and Tuesday are the load-bearing days.** If the week goes wrong, protect those two.
> A system with a working CI eval gate and nothing else is more employable than a system with
> everything else and no gate.

---

## `PRODUCTION.md`

The document that makes the work legible. Structure it like an engineer briefing a colleague.

```markdown
# Production readiness — Flutter Docs Assistant

## What it is
RAG over 1,847 Flutter/Dart documents. FastAPI + pgvector + Redis.
Deployed via Docker Compose. ~40 requests/day in personal use.

## Quality

**Eval suite:** 118 cases, 2 reps, stratified train/test (83/35).
**Noise floor:** ±7 points at 118 × 2. Changes smaller than that are not acted on.

| Metric | Train | Test |
|---|---:|---:|
| recall@10 | 0.88 | 0.86 |
| answer correctness (judge) | 0.84 | 0.82 |
| grounded (programmatic) | 0.97 | 0.96 |
| citation validity | 1.00 | 1.00 |
| correct refusal | 0.91 | 0.89 |

**Judge calibration:** 40 hand-labelled cases, 93% agreement. Two disagreements
were genuinely ambiguous; one was a judge error I fixed in v3 of the judge prompt.

**CI gate:** the PR suite (42 cases) must not drop more than 0.03 on any metric.
It has blocked 3 merges — two were real regressions, one was a threshold I'd set
too tight and subsequently loosened with justification.

## Safety

**Trifecta:** private data ✓ · untrusted content ✓ · outbound channel ✗
The outbound leg is deliberately absent — no tool makes a network request with
model-controlled parameters, and output filtering blocks non-allowlisted links
and all markdown images.

**Red-team suite:** 24 cases in CI.
- Injection targeting a write tool: attempted 4/10, blocked 10/10
- Cross-tenant data request: attempted 2/10, blocked 10/10 (session-scoped auth)
- Exfiltration via link: attempted 6/10, blocked 10/10 (domain allowlist)
- System prompt extraction: succeeded 3/10 — accepted; the prompt is not secret

**The result that matters:** prompt-level instructions alone never prevented an
attempt. Every block came from the architecture.

## Cost

| | |
|---|---|
| p50 / p95 / p99 per request | $0.0031 / $0.0079 / $0.0184 |
| Cache hit rate (prompt) | 71% |
| Cache hit rate (response) | 14% |
| Projected monthly at 10k req/day | $1,240 |
| Budget | $1,500, hard-stop → degrade to sources-only |

The p99 tail is conversations past turn 15, where history dominates input.
Trimming is in place; compaction is the next step.

## Operations

**Degradation, tested:**
| Dependency down | Behaviour |
|---|---|
| Reranker | Serves fused results. Recorded in trace. recall@10 −0.00, MRR −0.19 |
| Vector store | 503 with a clear message |
| Model rate-limited | Sources-only mode |
| Redis | Runs uncached. Cost ~3.4x |

**Rollback:** prompt version is an env var. Measured at 22 seconds, tested twice.
**Runbook:** [RUNBOOK.md]. Followed cold for a cost-spike drill; three steps were
unclear and have been rewritten.

## Known limitations
1. Multi-hop questions: 0.61 vs 0.89 on single-hop. Agentic retrieval would
   likely fix it; not yet worth the latency for my usage.
2. 12 scanned PDFs excluded — no OCR.
3. Semantic cache disabled. At threshold 0.95 the false-hit rate was 4%, which
   I judged too high for a documentation assistant where precision matters.

## What I'd do next
1. Compaction for long conversations — addresses the p99 cost tail directly.
2. OCR for the excluded PDFs — 12 documents is 8 of my remaining content gaps.
3. Agentic retrieval for multi-hop, if usage justifies the latency.
```

Read that document as a hiring manager would. **Every section demonstrates a distinct
competence**, and the "known limitations" section demonstrates the rarest one: knowing what your
system can't do and having decided that deliberately.

---

## Acceptance criteria

**The gate works**
- [ ] Push a deliberately worse prompt. CI blocks it. Screenshot it.
- [ ] The PR comment shows which metrics moved

**The traces work**
- [ ] Pick a random request. From its ID alone, determine what was retrieved, what prompt was
      built, what it cost, and whether the citations were valid — in under two minutes.

**The safety works**
- [ ] Every red-team case is green
- [ ] You can state attempted-vs-blocked numbers

**The economics work**
- [ ] You can state cost per request at p50 and p99, and what the tail contains
- [ ] Breaking the cache triggers an alert

**The operations work**
- [ ] Rollback performed and timed
- [ ] Every dependency killed in turn; behaviour recorded
- [ ] Runbook followed cold, and improved afterwards

---

## How to present it

### README order

1. **What it does** — two sentences
2. **The three headline numbers** — quality, cost, and something about safety. Near the top.
3. **A demo** — streaming, with citations
4. **[PRODUCTION.md](PRODUCTION.md)** — linked prominently
5. Quickstart · Architecture · Design decisions · What I'd do differently

### The interview answers

These are the questions. You now have real answers to all of them.

> **"How do you know it's good?"**
> 118 cases, held-out test set, the numbers, the judge calibration, and the noise floor —
> *"changes smaller than 7 points aren't acted on."* That last clause is what marks you as
> someone who's done this properly.

> **"What stops a bad change shipping?"**
> The CI gate. It has blocked three merges. Two were real.

> **"A user says the answer was wrong. What do you do?"**
> Walk the runbook: request ID → trace → was the answer in the retrieved context → which of the
> eight failure modes → add an eval case → fix → CI guards it forever.

> **"What happens when the provider goes down?"**
> The degradation table. Tested, not theorised.

> **"Is it secure?"**
> The trifecta audit, and the red-team numbers. Lead with: *"prompt-level instructions never
> prevented an attempt — every block came from the architecture."*

> **"What does it cost?"**
> p50, p99, monthly projection, what the tail contains, and what you'd do about it.

> **"What would you do differently?"**
> Your known-limitations list. Having one is the answer.

---

## 🎯 End of Week 26 — start applying

You have now done the thing almost nobody does. Chapter 1 promised this week, and here it is.

**This week, alongside finishing the project:**

- Update your CV around these five projects, led by outcomes and numbers
- Update your LinkedIn headline to what you're becoming, not what you were
- Pick 10 roles and apply to 3 of them **this week**

You are not finished learning — Part VI is six more weeks. **Apply anyway.** Interview processes
take weeks, you'll learn enormously from the first three interviews, and the feeling of being
ready arrives roughly two years after you actually are.

Chapter 31 covers portfolio and positioning properly. Don't wait for it.

---

## Before you start

**Protect Monday and Tuesday.** The eval suite and the CI gate are the deliverable. Everything
else supports them.

**Don't add features.** Not one. This week is about making what exists trustworthy, and every
hour spent on a new capability is an hour not spent on the thing that gets you hired.

**Write `PRODUCTION.md` as you go**, not on Sunday night. The numbers are easier to record when
you produce them.

---

<div align="center">

**[← Chapter 26](../ch26-deployment/)** · **[The Book](../../readme.md)** · **[Chapter 27 → Fine-Tuning](../../part-6-depth-and-edge/ch27-fine-tuning/)**

**End of Part V · Week 26 of 34 · 🎯 You are job-ready. Start applying.**

</div>
