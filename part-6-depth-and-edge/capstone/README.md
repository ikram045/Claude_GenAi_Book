# 🏆 Capstone

### Weeks 31–34 · ~88 hours · One product, shipped publicly

---

## The brief

Build and publicly ship **one product** that only you could have built: an AI system with a real
backend, measured quality, and a mobile app — the full stack of what this book taught, aimed at a
problem you actually care about.

Projects A–E each proved one thing. **This proves you can do all of it at once, for real users,
and finish.**

> **The bar is not "impressive." The bar is *shipped, used, and measured.***
>
> A modest product with ten real users, an eval suite and a cost dashboard beats an ambitious
> half-finished one every time — with hiring managers, and with you.

---

## Choosing it

Four criteria. All four matter.

**1 · You'd use it yourself, weekly.** The single best predictor of finishing. You will hit a
wall in week 33; wanting the thing is what gets you past it.

**2 · It genuinely needs what you know.** Retrieval over a real corpus, or an agent doing real
work. If a simple API call would do, it won't demonstrate anything.

**3 · Mobile is natural, not bolted on.** The app should be the *right* interface — because it's
with you, because it works offline, because it's voice, because it uses the camera.

**4 · The scope fits four weeks.** Ruthlessly. You will underestimate by about half.

### Strong shapes

| Product | Why it works |
|---|---|
| **A personal knowledge assistant** | Your notes, bookmarks, saved articles. Offline on-device search, cloud for hard questions. You'd use it daily |
| **A documentation companion for a framework you know** | Flutter is the obvious one. A real audience, a messy corpus, and you can judge every answer |
| **A field-work assistant** | Camera + vision + a domain corpus, working offline. Mobile is genuinely required |
| **A voice research assistant** | Ask while walking, get a cited answer. Chapter 29's latency work, applied |
| **A codebase companion** | Agent over your repos, approvals from your phone. Chapter 30's approval UI, used for real |

### Shapes to avoid

- **"An AI assistant for everything."** No scope, no evaluation, no story.
- **Anything needing a corpus you don't have.** Data acquisition will eat all four weeks.
- **A clone of a well-funded product.** You'll be compared to it and lose.

---

## Requirements

### It must actually work

- [ ] Deployed and reachable, not localhost
- [ ] The mobile app installable — TestFlight, an APK, or a store listing
- [ ] **At least five real users who are not you.** Friends count. Usage doesn't lie
- [ ] Running for at least two weeks before you call it done

### It must be measured

- [ ] An eval suite of 80+ cases, in CI, with a gate
- [ ] Retrieval or task metrics reported on a held-out set
- [ ] Cost per request, p50 and p99
- [ ] Real usage metrics from real users

### It must be safe

- [ ] Threat model and trifecta audit
- [ ] Red-team suite in CI
- [ ] Rate limits and budgets — **you're paying for strangers' requests now**
- [ ] PII handled properly; a privacy note users can read

### It must be operable

- [ ] Traces on every request
- [ ] Alerts that reach you
- [ ] A runbook
- [ ] Rollback tested

### It must show your edge

- [ ] The mobile app is a first-class surface, not a wrapper
- [ ] **Something works offline or on-device**
- [ ] Streaming holds frame rate, measured
- [ ] Mobile-specific handling: backgrounding, network loss, battery

---

## The four weeks

| Week | Focus | Deliverable |
|:---:|---|---|
| **31** | Backend | Corpus ingested, retrieval working, baseline measured, API deployed |
| **32** | App | Streaming, citations, offline mode, on-device path. In someone else's hands |
| **33** | Hardening | Evals in CI, red team, tracing, budgets, runbook. **Real users invited** |
| **34** | Polish and tell | Fix what users hit, write it up, record the demo, publish |

> **Get it into someone else's hands by the end of week 32.** Not week 34. Real users find
> problems you cannot imagine, and you need two weeks to respond to them. A product that met
> users only on the last day hasn't really shipped.

### Week 33 is the one that matters

The temptation in week 33 is to add features. **Don't.** Week 33 is evals, security, tracing and
budgets — the things that make it a *system* rather than a demo, and the things you'll talk about
in interviews.

---

## The write-up

Four documents. Together they're the strongest thing in your portfolio.

**`README.md`** — what it is, the headline numbers, a demo, how to try it.

**`PRODUCTION.md`** — Project E's structure: quality, safety, cost, operations, known limitations.

**`FINDINGS.md`** — what you measured, what each change was worth, what you reverted.

**`RETROSPECTIVE.md`** — the rarest and most valuable one:

```markdown
# Retrospective

## What I set out to build
## What I actually built, and where they differ
## What real users did that I didn't expect
## What broke in production
## What I'd do differently
## What I learned that I couldn't have learned from a tutorial
```

**That fourth document is what a senior engineer writes** and what almost no career-switcher
produces. The "what real users did that I didn't expect" section alone will be more interesting
than most candidates' entire portfolios.

---

## The demo

Record it. Three minutes, maximum.

```
 0:00  What it does and who it's for            (15s)
 0:15  The core loop, working                   (60s)  ← streaming, citations
 1:15  The differentiator                       (45s)  ← offline / on-device / voice
 2:00  Behind it: eval dashboard, traces, cost  (45s)  ← nobody shows this. Do.
 2:45  What's next                              (15s)
```

**That 2:00 segment is the one that gets you hired.** Everyone demos the chat interface. Almost
nobody shows the eval dashboard, the trace of a request, and the cost per query — and those are
what prove it's engineering rather than a wrapper.

---

## Publishing

**Ship it publicly.** The point isn't traffic; it's that you finished something real and put your
name on it.

- GitHub, with all four documents
- A short post: what you built, what you measured, what surprised you
- Share it where the people who'd use it are
- Tell the five users what changed because of their feedback

---

## When you're done

You will have:

- **Six systems**, one of them used by real people
- **A measured quality story** for every one of them
- **~34 public posts** documenting the whole journey
- **A capability almost nobody else has** — the full stack of an AI product, including the app

And you'll be four weeks into a job search that started at week 26, with something new and
genuinely interesting to talk about.

---

## One last thing

Go back and read [`my-why.md`](../../part-1-foundations/ch01-orientation/my-why.md).

You wrote it on week one, to the version of you who'd be tired and doubting in month four. You
probably were. You kept going anyway.

Check it against where you actually are. Some of it will have been wrong — the target date, the
job title, what you thought you'd enjoy. That's fine, and noticing it is the point.

Then write a new one, for the next eight months.

---

<div align="center">

**[← Chapter 31](../ch31-portfolio/)** · **[The Book](../../readme.md)** · **[Roadmap](../../ROADMAP.md)**

**End of the book · Week 34 of 34**

*You started as a Flutter developer who wanted to work on AI.
You're now someone who builds AI systems and can prove they work.*

**Go get the job.**

</div>
