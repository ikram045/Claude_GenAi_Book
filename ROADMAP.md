# The Roadmap

### Week by week, from Flutter developer to AI Application Engineer

---

## The honest timeline

At **~22 hours per week**, this curriculum runs **34 weeks** — about eight months.

That number is longer than the six months you'll see promised elsewhere, and I want to be
straight with you about why. Six months is achievable if you skip evaluation, skip
production concerns, and build four impressive demos. People do exactly that, and then
they fail the interview question *"how do you know your RAG system is actually good?"* —
because there is no answer to that question that you can bluff.

So here is the structure, and the important thing about it:

> **You start applying for jobs at the end of Week 26**, when Parts I–V are done.
> **Part VI runs in parallel with your job search**, not before it.

That gives you the six-month job-ready mark you were aiming for, *and* the depth. You
don't have to choose.

---

## The map

```
  PART I          PART II         PART III        PART IV         PART V          PART VI
  Foundations     Models          Retrieval       Agents          Production      Depth
  ▓▓▓▓            ▓▓▓▓▓           ▓▓▓▓▓▓          ▓▓▓▓▓▓          ▓▓▓▓▓           ▓▓▓▓▓▓▓▓
  W1────W4        W5────W9        W10───W15       W16───W21       W22──W26        W27────W34
                                                                       ↑
                                                              START APPLYING HERE
```

---

## Part I — Foundations
### Weeks 1–4 · *Python stops being a foreign language*

You are not learning to program. You already know how. You are learning a second dialect,
and you'll move far faster than a beginner because every concept has a Dart counterpart
waiting for it.

| Week | Chapter | Hours | You finish able to |
|:---:|---|:---:|---|
| **1** | [Ch 1 · Orientation](part-1-foundations/ch01-orientation/)<br>[Ch 2 · Python for Dart Developers](part-1-foundations/ch02-python-for-dart-devs/) | 22 | Read and write idiomatic Python; explain what the job actually is |
| **2** | [Ch 3 · The Modern Toolchain](part-1-foundations/ch03-modern-toolchain/) | 22 | Set up a real project: `uv`, ruff, mypy, pytest, proper layout |
| **3** | [Ch 4 · Async & FastAPI](part-1-foundations/ch04-async-and-fastapi/) | 22 | Serve HTTP, stream responses, run background work |
| **4** | 🔨 [**Project A** · Typed, tested, containerized API](part-1-foundations/project-a-typed-api/) | 22 | Ship Python you'd be comfortable showing a senior engineer |

> **Why so much setup before any AI?** Because the difference between someone who "did an
> LLM tutorial" and someone employable is almost entirely visible in the code *around* the
> model call. Four weeks now saves you from six months of writing scripts that nobody
> would merge.

---

## Part II — Language Models
### Weeks 5–9 · *LLMs stop being magic and become a component you control*

| Week | Chapter | Hours | You finish able to |
|:---:|---|:---:|---|
| **5** | [Ch 5 · What an LLM Actually Is](part-2-language-models/ch05-what-an-llm-is/) | 22 | Explain tokens, embeddings, attention and sampling to another engineer |
| **6** | [Ch 6 · Talking to Models](part-2-language-models/ch06-talking-to-models/) | 22 | Use the Claude API properly: streaming, system prompts, multi-turn |
| **7** | [Ch 7 · Prompting as Engineering](part-2-language-models/ch07-prompting-as-engineering/) | 22 | Write, version and test prompts like source code |
| **8** | [Ch 8 · Structured Output](part-2-language-models/ch08-structured-output/)<br>[Ch 9 · Context, Cost & Latency](part-2-language-models/ch09-context-cost-latency/) | 22 | Get reliable JSON out of a model; reason in tokens and dollars |
| **9** | 🔨 [**Project B** · Streaming CLI assistant](part-2-language-models/project-b-streaming-assistant/) | 22 | Build something you personally use every day |

> **The mindset shift happens here.** Chapter 5 is where you stop thinking of the model as
> an oracle and start thinking of it as a very fast, very well-read intern with no memory
> and a tendency to guess confidently. Everything downstream depends on that shift.

---

## Part III — Retrieval
### Weeks 10–15 · *You can make a model answer from your data, and prove it works*

Six weeks, not four. Retrieval is the single most demanded skill in AI application
engineering, and it is the one most people do badly — because every tutorial stops at
"chunk it, embed it, search it," which produces a system that works on your demo file and
falls apart on your company's actual documents.

| Week | Chapter | Hours | You finish able to |
|:---:|---|:---:|---|
| **10** | [Ch 10 · Embeddings, Deeply](part-3-retrieval/ch10-embeddings-deeply/) | 22 | Explain what a vector *means* and pick an embedding model on purpose |
| **11** | [Ch 11 · Document Processing & Chunking](part-3-retrieval/ch11-chunking/)<br>[Ch 12 · Vector Databases](part-3-retrieval/ch12-vector-databases/) | 22 | Turn messy PDFs/HTML/code into good chunks; run pgvector and Qdrant |
| **12** | [Ch 13 · Search That Actually Works](part-3-retrieval/ch13-search-that-works/) | 22 | Build hybrid BM25 + vector search with reranking |
| **13** | [Ch 14 · Measuring Retrieval](part-3-retrieval/ch14-measuring-retrieval/) | 22 | Build a gold set; compute recall@k, MRR, nDCG; improve a number |
| **14** | [Ch 15 · RAG Architectures & Failure Modes](part-3-retrieval/ch15-rag-architectures/) | 22 | Diagnose the eight ways RAG breaks, by symptom |
| **15** | 🔨 [**Project C** · Production RAG](part-3-retrieval/project-c-production-rag/) | 22 | Show a retrieval score and the story of how you raised it |

> **Chapter 14 is the most important chapter in Part III.** Not the most interesting — the
> most important. Anyone can build retrieval. Almost nobody can tell you whether theirs is
> any good. Be the person who can.

---

## Part IV — Agents
### Weeks 16–21 · *Models stop answering and start acting*

| Week | Chapter | Hours | You finish able to |
|:---:|---|:---:|---|
| **16** | [Ch 16 · Tool Use](part-4-agents/ch16-tool-use/) | 22 | Design tool schemas a model can actually use correctly |
| **17** | [Ch 17 · The Agent Loop](part-4-agents/ch17-the-agent-loop/) | 22 | Write an agent loop from scratch; handle termination and recovery |
| **18** | [Ch 18 · Memory & State](part-4-agents/ch18-memory-and-state/) | 22 | Give an agent short- and long-term memory that doesn't blow the context window |
| **19** | [Ch 19 · MCP](part-4-agents/ch19-mcp/) | 22 | Build an MCP server and connect it to a real client |
| **20** | [Ch 20 · Multi-Agent Systems](part-4-agents/ch20-multi-agent/)<br>[Ch 21 · Frameworks](part-4-agents/ch21-frameworks/) | 22 | Know when multi-agent helps, when it's theatre, and which framework to reach for |
| **21** | 🔨 [**Project D** · Multi-tool agent](part-4-agents/project-d-multi-tool-agent/) | 22 | Demonstrate autonomy *with* guardrails |

> **You write the raw loop in Chapter 17 before you touch a framework in Chapter 21.**
> This ordering is deliberate and non-negotiable. Frameworks are wonderful when you know
> what they abstract; they are a career-limiting crutch when you don't.

---

## Part V — Production
### Weeks 22–26 · *You become hireable*

⭐ **If you only have time for one part of this book, it is this one.**

Everything before this teaches you to build. This part teaches you to be *trusted* with
what you built — and that is the gap that separates a candidate with an impressive GitHub
from a candidate with an offer.

| Week | Chapter | Hours | You finish able to |
|:---:|---|:---:|---|
| **22** | [Ch 22 · Evals](part-5-production/ch22-evals/) | 22 | Build a real eval suite: datasets, LLM-as-judge, CI regression gates |
| **23** | [Ch 23 · Observability & Tracing](part-5-production/ch23-observability/) | 22 | Debug a non-deterministic system from traces instead of guesses |
| **24** | [Ch 24 · Security](part-5-production/ch24-security/) | 22 | Defend against prompt injection, exfiltration and unsafe tool use |
| **25** | [Ch 25 · Performance & Cost](part-5-production/ch25-performance-and-cost/)<br>[Ch 26 · Deployment](part-5-production/ch26-deployment/) | 22 | Cut a bill 10x; deploy with queues, limits and safe prompt rollout |
| **26** | 🔨 [**Project E** · Take C or D to production](part-5-production/project-e-to-production/) | 22 | Present a system with tests, traces, evals and a cost dashboard |

> ### 🎯 End of Week 26: start applying.
> You are now more qualified than most people interviewing for these roles, because you
> can answer the question they all fail. Do not wait for Part VI. Do not wait until you
> "feel ready" — that feeling arrives roughly two years after you actually are.

---

## Part VI — Depth & Your Edge
### Weeks 27–34 · *You become distinctive* · **Runs in parallel with your job search**

| Week | Chapter | Hours | You finish able to |
|:---:|---|:---:|---|
| **27** | [Ch 27 · Fine-Tuning](part-6-depth-and-edge/ch27-fine-tuning/) | 22 | Run a LoRA fine-tune — and argue convincingly for *not* doing one |
| **28** | [Ch 28 · Local & Open Models](part-6-depth-and-edge/ch28-local-models/)<br>[Ch 29 · Multimodal](part-6-depth-and-edge/ch29-multimodal/) | 22 | Self-host with vLLM/Ollama; build vision and voice pipelines |
| **29** | [Ch 30 · Your Flutter Edge](part-6-depth-and-edge/ch30-flutter-edge/) | 22 | Run inference on-device; design AI UX that handles latency and failure |
| **30** | [Ch 31 · Portfolio & Positioning](part-6-depth-and-edge/ch31-portfolio/) | 22 | Present your work so a hiring manager understands it in 90 seconds |
| **31–34** | 🏆 [**Capstone**](part-6-depth-and-edge/capstone/) + interview practice | 22 | Ship one serious product: mobile + backend + evals |

> **Chapter 30 is your unfair advantage.** There are perhaps a few thousand people in the
> world who can build a competent RAG pipeline *and* ship a polished mobile app that uses
> it. Most GenAI engineers hand their API to someone else and hope. You won't have to.

---

## What to do when you fall behind

You will. Everyone does. Here's the triage order, and it matters:

1. **Never skip Part V.** Evals and production are the hireable part. If you're short on
   time, take it from Part VI, then Part IV.
2. **Projects beat chapters.** If you must choose, build the project and skim the chapter.
   Understanding sticks to things you made; it slides off things you read.
3. **A short week beats a skipped week.** Ninety minutes on a terrible week keeps the
   thread alive. Two consecutive zero weeks is how this quietly ends.
4. **Repeating a week is not failure.** If Chapter 14's checkpoint defeats you, spend
   another week there. The schedule is a servant, not a judge.

---

## The one metric that matters

Not chapters read. Not hours logged. This:

> **Can you pass the checkpoint at the end of the chapter, without looking anything up?**

Everything else in this document is scaffolding around that single question.

---

<div align="center">

**[← Back to the book](readme.md)** · **[Start Chapter 1 →](part-1-foundations/ch01-orientation/)**

</div>
