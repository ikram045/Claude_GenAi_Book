# Chapter 31 · Portfolio & Positioning

### Making eight months of work legible in ninety seconds

> **Week 30 · ~22 hours · You should already be applying**
>
> If you followed the roadmap you started applying at Week 26. This chapter sharpens the
> presentation. If you haven't started — start this week, before you finish reading.

---

## 31.0 · Why this chapter exists

You have built a great deal. The problem is that **nobody will read it.**

A hiring manager spends ninety seconds on your application. A recruiter spends twenty. An
interviewer skims your README in the five minutes before the call.

Eight months of genuine work loses to a worse candidate with a clearer story, routinely. This
chapter is about not losing that way.

---

## 31.1 · What you actually have

Take stock, because you've probably lost track — and because you can't present what you can't
enumerate.

**Five systems:** a typed API, a streaming assistant, a measured RAG system, a guarded agent, and
one of those deployed to production standard.

**Artefacts most candidates don't have:**

- A gold set and an ablation table showing what each change was worth
- A judge calibrated against human labels, with the agreement number
- A CI gate that has blocked real regressions
- A red-team suite with attempt-versus-blocked numbers
- A cost ladder taking a real workload from $3,150 to $558
- A threat model and a trifecta audit
- A runbook you've followed
- ~30 public posts documenting the whole thing
- An AI-powered mobile app with measured frame rates and on-device throughput

**Judgment you can demonstrate:**

- Why you *didn't* use multi-agent, with data
- Why you reverted HyDE, with latency numbers
- Why fine-tuning was the wrong answer for your problem
- Where your remaining failures are and which are unfixable by engineering

> **That last group is what actually distinguishes you.** Anyone can list technologies. Very few
> candidates can explain a decision they made *against* the popular option, with measurements.

---

## 31.2 · Your positioning

One sentence that makes you memorable and easy to place.

```
❌ "Software engineer transitioning into AI."
     Generic. Says what you're leaving, not what you bring.

❌ "AI Engineer | LLM | RAG | LangChain | Vector DB | Prompt Engineering"
     Keyword soup. Says nothing.

✅ "AI application engineer who builds retrieval systems with measured quality —
    and ships the mobile apps that use them."
```

The good version does three things: names the role, names the differentiator (*measured*), and
names the rare capability (*mobile*).

### Lead with the combination, always

```
   "I spent three years shipping Flutter apps, then eight months building
    production LLM systems. I can build a RAG pipeline, prove it works with
    an eval suite, deploy it with CI gates — and ship the app that uses it,
    including on-device inference for the offline case."
```

**Never apologise for the Flutter years.** They are not a gap. They're the reason you understand
latency, offline behaviour, streaming UX, and shipping to real users — and they're the reason
you're the only candidate who can do the mobile half.

---

## 31.3 · Three projects, not eight

Chapter 1's Demo Trap, resolved. **One evaluated system beats eight demos**, and three is the
maximum anyone will look at.

| Slot | Project | What it proves |
|---|---|---|
| **1 · The flagship** | Project E — production RAG | Everything. Lead with this |
| **2 · The range** | Project D — the guarded agent | Autonomy, safety, judgment |
| **3 · The differentiator** | The Flutter app | The combination nobody else has |

**Archive the rest.** Projects A and B taught you things; they don't belong on a CV next to
Project E, where they make the strong work look weaker by association.

### The flagship README

The order matters, because people stop reading:

```markdown
# Flutter Docs Assistant

RAG over 1,847 Flutter documents. Answers with citations, refuses when it
doesn't know, deployed with evals in CI.

**recall@10 of 0.86 on a held-out test set of 35 queries, up from 0.58 at
baseline. $0.0031 per request at p50. CI blocks any change that regresses
quality by more than 3 points.**

[30-second demo gif — streaming, with a citation being tapped]

→ [PRODUCTION.md](PRODUCTION.md) — quality, safety, cost and operations
→ [FINDINGS.md](FINDINGS.md) — what each change was worth, and what I reverted

## Quickstart
...
```

**The numbers go in the first screen.** They are the reason someone keeps reading, and they're
the thing almost no other repository has.

---

## 31.4 · The CV

One page. Outcomes, not activities.

```
❌ "Worked with RAG, vector databases, and prompt engineering"
✅ "Built a RAG system over 23K document chunks; raised recall@10 from 0.58 to
    0.86 via hybrid search and reranking, measured on a held-out eval set"

❌ "Implemented an AI agent with tool use"
✅ "Built a tool-using agent with permission gating and budget caps; red-team
    testing showed prompt-level defences never blocked an injection attempt —
    all 10 were stopped by the permission layer"

❌ "Optimised LLM costs"
✅ "Cut a production workload from $3,150 to $558/month; prompt caching and
    retrieval trimming accounted for over half, with no measured quality loss"
```

Each good version contains a number, a method, and a result. **The second one is memorable
because it describes a finding, not a task.**

### Structure

1. **Positioning line** — section 31.2
2. **Selected projects** — three, with numbers
3. **Experience** — including the Flutter years, framed as engineering depth
4. **Skills** — grouped, honest. Only list things you'd survive an hour of questions about
5. **Writing** — link your blog if you kept the Sunday habit

---

## 31.5 · Online presence

**GitHub.** Pin three repositories. Every pinned repo has a README with numbers in the first
screen. Prune everything else from view — a pinned half-finished tutorial repo actively hurts.

**LinkedIn.** Headline is your positioning sentence. The About section is the paragraph from
31.2. Post occasionally about what you built, with numbers.

**Writing.** If you kept the Sunday habit, you have ~30 posts. That's a genuine asset — evidence
of sustained learning and the ability to explain technical work.

The posts that perform, in order:

1. **"What I measured"** — an ablation table with honest conclusions
2. **"What didn't work"** — rarer than success posts and more trusted
3. **"The thing nobody told me"** — the post-filtering bug, the streaming reflow, the
   compaction-content trap
4. Tutorials — least differentiating; everyone writes these

> **One genuinely good post about something you measured is worth thirty tutorial posts.**

---

## 31.6 · The interview, mapped

Here are the questions, with where your answer lives. Rehearse each one **out loud** — reading
them is not the same.

| Question | Your answer |
|---|---|
| "How do you know your RAG system is good?" | Ch 14 · gold set, held-out test, the numbers, **and the noise floor** |
| "What was your biggest improvement?" | Ch 14 · reranking — and why recall didn't move |
| "What didn't work?" | Ch 13 · HyDE, with latency and cost numbers |
| "How do you stop a bad prompt shipping?" | Ch 22 · the CI gate, and the three merges it blocked |
| "How do you debug a wrong answer?" | Ch 23 · request ID → trace → which of the eight failure modes |
| "Is it secure?" | Ch 24 · trifecta audit, and "only the architecture blocked it" |
| "What does it cost?" | Ch 9/25 · p50, p99, what the tail contains, and the ladder |
| "Would you use multiple agents?" | Ch 20 · "I measured it. No, and here's why" |
| "Would you fine-tune?" | Ch 27 · the decision memo, probably concluding no |
| "How would you scale to 10M chunks?" | Ch 12 · quantization before sharding, the memory arithmetic |
| "What happens when the provider is down?" | Ch 26 · the degradation table, tested |
| "How do you handle prompt injection?" | Ch 24 · architecturally; prompt defences are friction |
| "Why are you switching careers?" | Ch 1 · your `my-why.md`, told honestly |

### The two patterns that win

**Lead with a measurement.** *"Recall went from 0.71 to 0.87"* opens a conversation. *"I used
hybrid search"* closes one.

**Volunteer what didn't work.** Candidates present only successes. Saying *"I tried HyDE, it cost
430ms for one point of recall, I reverted it"* signals judgment and honesty simultaneously, and
it's memorable because almost nobody does it.

### The take-home

If you get one, it's usually "build a small RAG system" or "build an agent." You can do that in
an afternoon. **Spend the remaining time on the thing they didn't ask for:**

- A small eval set and a measured result
- A README explaining your design decisions and their alternatives
- One honest paragraph on what you'd do with more time

**That's what separates a pass from an offer.** Everyone submits working code. Almost nobody
submits evidence that it works.

---

## 31.7 · The search itself

**Titles to search:** AI Engineer · AI Application Engineer · LLM Engineer · Machine Learning
Engineer (Applied) · Forward Deployed Engineer · AI Product Engineer.

**Where the roles are:** AI-native startups (fastest, least process, most learning), product
companies adding AI (your mobile background is a genuine advantage here), agencies and
consultancies (variety, good for building range), and — often overlooked — **the company you
already work at.** An internal move is the easiest transition available and people forget to try
it.

**How to apply:**

- **Quality over volume.** Ten considered applications beat a hundred generic ones.
- **Read the posting and match your framing** to what they actually need.
- **A short cover note that leads with a number** and a link to the flagship README.
- **Referrals, wherever possible.** Your ~30 posts are the reason someone might know your name.

**Expect a long pipeline.** Weeks per process, multiple rounds, rejections that mean nothing in
particular. Apply steadily rather than in bursts, and **keep building while you interview** —
having something new to say in week six of a search is worth more than polishing.

---

## 31.8 · Checkpoint

> **You're ready when all of these are true.**

**Have:**

1. A positioning sentence you can say without hesitating.
2. Three pinned repositories, each with numbers in the first screen.
3. A one-page CV with a number in every project bullet.
4. A LinkedIn headline that isn't keyword soup.

**Can, out loud, in 90 seconds each:**

5. Explain your flagship project and its headline numbers.
6. Answer *"how do you know it's good?"*
7. Describe something you tried and **reverted**, with the data.
8. Explain why you're switching, honestly.

**Doing:**

9. Applying to at least three roles a week.
10. Still building.

---

## 31.9 · Going deeper (optional)

**Read job postings as a curriculum**, not as a judgment. Requirements you don't meet are a
reading list, and the list is shorter than it looks.

**Do mock interviews.** With a friend, or out loud to yourself. The gap between knowing something
and explaining it under mild pressure is larger than anyone expects.

**Keep the Sunday habit through the search.** It's how you have something new to say in month
three, and it's how people find you without you applying.

---

<div align="center">

**[← Chapter 30](../ch30-flutter-edge/)** · **[The Book](../../readme.md)** · **[🏆 Capstone →](../capstone/)**

*Chapter 31 of 31 · Week 30*

</div>
