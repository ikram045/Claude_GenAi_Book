# From Flutter to Generative AI

### A working engineer's book on building real GenAI systems

---

This is not a course. It is not a tutorial series. It is a **book you build**, written for
one specific reader: a competent mobile developer who already knows how to ship software,
and now wants to become an **AI Application Engineer**.

You already know the hard parts of engineering. You know what it feels like to own a bug
at 11pm, to argue about state management, to ship something real to real users. That is
worth more than you think, and most of this book is written on the assumption that you
have it.

What you don't yet have is Python fluency, a mental model of how language models actually
behave, and — most importantly — the **evaluation mindset** that separates people who make
demos from people who get hired.

That's what the next 34 weeks are for.

---

## Who this is for

> A Flutter/Dart developer with 1+ years of real shipping experience, moving into
> LLM application engineering. No machine learning background assumed.
> No university mathematics assumed.

If you know what a `Future` is, what dependency injection is for, and why global mutable
state ruins your week — you have enough to start Chapter 1 today.

---

## What you will be able to do at the end

Not "understand." **Do.** Every one of these is a checkpoint you must physically pass:

- Build and ship a production RAG system over real documents, with measured retrieval
  quality you can defend in an interview.
- Build agents that use tools, recover from their own mistakes, and know when to stop.
- Write an evaluation suite that runs in CI and blocks a bad prompt from reaching users.
- Reason precisely about tokens, latency, and cost — and cut a system's bill by 10x
  without cutting quality.
- Debug a non-deterministic system, which is a genuinely different skill from debugging
  a deterministic one.
- Explain, at a whiteboard, why your retrieval returns what it returns.

And because of where you came from: **ship all of that inside a mobile app**, which
almost nobody else in this field can do.

---

## How the book is organised

Six parts, thirty-one chapters, five projects, one capstone.

| Part | Title | Weeks | What changes in you |
|:---:|---|:---:|---|
| **I** | [Foundations](part-1-foundations/) | 1–4 | Python stops being a foreign language |
| **II** | [Language Models](part-2-language-models/) | 5–9 | LLMs stop being magic and become a component you control |
| **III** | [Retrieval](part-3-retrieval/) | 10–15 | You can make a model answer from *your* data, and prove it works |
| **IV** | [Agents](part-4-agents/) | 16–21 | Models stop answering and start *acting* |
| **V** | [Production](part-5-production/) | 22–26 | You become hireable |
| **VI** | [Depth & Your Edge](part-6-depth-and-edge/) | 27–34 | You become distinctive |

📍 **The full week-by-week plan lives in [ROADMAP.md](ROADMAP.md).**
📈 **Track yourself in [PROGRESS.md](PROGRESS.md).** Update it every Sunday. Non-negotiable.

---

## How to read a chapter

Every chapter has the same seven-part spine. It never changes, so you always know where
you are:

```
1. Why this exists      →  The problem, before the solution. Always.
2. The mental model     →  An analogy, usually borrowed from Flutter or everyday life.
3. How it actually works→  The real mechanism. No hand-waving.
4. Build it             →  Code you type yourself. Do not copy-paste.
5. Exercises            →  Small tasks with tests that must go green.
6. Checkpoint           →  "You may move on when you can do X without looking it up."
7. Going deeper         →  Optional appendix + a short, curated reading list.
```

**The rules of this book:**

1. **Type the code. Never paste it.** Your fingers learn things your eyes don't. This
   sounds like folklore. It isn't — you will discover three bugs per chapter purely
   because you typed it out and something didn't look right.
2. **Do not skip the checkpoint.** If you can't pass it, you haven't finished the chapter,
   no matter how many pages you read.
3. **Break the examples on purpose.** Change a number, delete a line, feed it garbage.
   Understanding a system means knowing how it fails, and you learn that fastest by
   causing the failure yourself.
4. **Write every Sunday.** Two paragraphs on what you learned, published somewhere public.
   By week 34 you will have 34 posts, which is a portfolio you built for free while
   studying.

---

## Your weekly rhythm (~22 hours)

| Day | Hours | Work |
|---|:---:|---|
| Mon–Thu | 2 each | Read and code the chapter |
| Fri | 2 | Exercises until the tests pass |
| Sat | 5 | Project work — the real building |
| Sun | 2 | Write your post, update `PROGRESS.md`, plan the week |

Some weeks you'll do 30 hours because you're excited. Some weeks you'll do 8 because life
happened. Both are fine. **The only failure mode is a week with zero.** A single hour on a
bad week keeps the thread alive; zero hours twice in a row is how people quit without ever
deciding to.

---

## The projects

Five projects and a capstone. These are the things you will actually show people.

| | Project | After chapter | What it proves |
|:---:|---|:---:|---|
| **A** | Typed, tested, containerized API | 4 | You write real Python, not script Python |
| **B** | Streaming CLI assistant with cost tracking | 9 | You understand the model as an engineering component |
| **C** | Production RAG with measured quality | 15 | You can build the single most in-demand system in the field |
| **D** | Multi-tool agent that does real work | 21 | You understand autonomy and its limits |
| **E** | Project C or D, taken to production | 26 | **The one that gets you hired** |
| **🏆** | Capstone — mobile + backend + evals | 31 | Your entire interview story in one link |

---

## What this book deliberately refuses to do

Being clear about what's *not* here is as useful as listing what is.

- **It will not start with mathematics.** Linear algebra and calculus are in the
  [appendices](appendices/), available the moment you're curious. Front-loading them is
  the single most common reason career switchers quit in month two.
- **It will not teach you to train models from scratch.** That is a different job. You
  will fine-tune in Chapter 27, and you will learn the far more valuable skill of knowing
  *when not to*.
- **It will not start with a framework.** You will write raw agent loops with your own
  hands before you are allowed to touch LangGraph. Frameworks are excellent once you know
  what they're hiding; they are a trap before that.
- **It will not teach classical ML.** Regression, decision trees, scikit-learn. Genuinely
  useful knowledge, almost never needed for the job you're targeting.
- **It will not pretend this field is stable.** Specific model names and prices in this
  book will age. The *mental models* — how retrieval fails, why evals matter, what a
  token costs you in latency — will not.

---

## Before Chapter 1

Nothing. Open [Chapter 1](part-1-foundations/ch01-orientation/) and read. Environment
setup is Chapter 3's job, deliberately — because the fastest way to lose a career switcher
is to make their first evening a fight with a Python installation.

---

## The appendices

Optional deep dives. Read when curious, never as a prerequisite.

| | Title | Pairs with |
|:---:|---|---|
| A | [The Mathematics of Attention](appendices/) | Chapter 5 |
| B | [Vector Mathematics](appendices/) | Chapter 10 |
| C | [How Fine-Tuning Actually Works](appendices/) | Chapter 27 |

---

<div align="center">

**Start here → [Chapter 1: Orientation](part-1-foundations/ch01-orientation/)**

*Week 1 of 34. Job-ready at week 26. Let's go.*

</div>
