# Chapter 20 · Multi-Agent Systems

### Mostly you shouldn't. Here's the narrow case where you should, and why.

> **Week 20, part 1 · ~11 hours**
>
> The most over-applied pattern in the field. This chapter spends its first half arguing
> against multi-agent architectures, because that argument is the useful part — and then
> shows you the genuine wins, which are narrower and more specific than the hype suggests.

---

## 20.0 · Why this chapter exists

Search for AI agent architectures and you'll find diagrams full of specialists: a Researcher, a
Writer, a Critic, a Manager, all conversing. It looks like an organisation chart. It feels
sophisticated.

Most of the time it is **slower, more expensive, harder to debug, and less reliable** than one
agent with the same tools.

That's not contrarianism. It's what the failure modes predict, and what people report after
shipping. But there *is* a real case for multi-agent systems — it's just not "specialists
collaborate." It's much more boring and much more useful:

> **Multi-agent is primarily a context management technique.**
>
> A subagent reads a great deal and returns a little. That's the win. Everything else is
> usually theatre.

Once you see it that way, the decision becomes clear, and this chapter becomes short.

---

## 20.1 · What it actually means

```
   SINGLE AGENT                    MULTI-AGENT

   ┌─────────┐                     ┌──────────────┐
   │  agent  │                     │ orchestrator │
   └────┬────┘                     └──┬───┬───┬───┘
        │ tools                       │   │   │
   ┌────┴────┬────────┐          ┌────┘   │   └────┐
   search  write  analyse     ┌──┴──┐  ┌──┴──┐  ┌──┴──┐
                              │ sub │  │ sub │  │ sub │
   One context.               └─────┘  └─────┘  └─────┘
   One history.
                              Separate contexts.
                              Communication by message.
```

The defining property isn't specialisation — a single agent can be prompted to behave like a
specialist. **It's that each agent has its own context window.** That's the thing you're buying,
and everything good and bad about multi-agent follows from it.

---

## 20.2 · The case against

Five reasons, in order of how often they bite.

### 1 · Information is lost at every boundary

An agent has a rich working context: the original request, what it's tried, what failed, the
nuance in the user's phrasing. When it delegates, all of that has to be compressed into a
message.

```
Orchestrator knows:  the full request, three failed approaches, a constraint
                     the user mentioned in passing, the tone they want

Subagent receives:   "Research the refund policy for enterprise customers."
```

The subagent does competent work on the wrong problem, because it never learned the constraint.
This is the **single most common multi-agent failure**, and it's structural — not a bug you can
fix, a property you have to design around.

### 2 · Cost multiplies

Every agent runs its own loop with its own growing history. Four agents doing three iterations
each is twelve model calls, plus the orchestrator's own loop, plus the token cost of passing
messages around.

**Three to ten times the cost of a single agent** is typical for the same task.

### 3 · Debugging gets much harder

A single agent produces one trace. You read it top to bottom.

A multi-agent system produces N interleaved traces plus a communication log. When the output is
wrong, you have to determine: which agent was wrong? Or was it told the wrong thing? Or did it
do fine work that the orchestrator misread?

That's a categorically harder debugging problem, and you'll do it often.

### 4 · Coordination failures are their own category

Beyond the failure modes each agent already has, you get new ones: agents duplicating work,
agents waiting on each other, an orchestrator that misreads a subagent's result, contradictory
conclusions with no resolution mechanism.

### 5 · The specialisation is usually imaginary

"Researcher," "Writer" and "Critic" are typically the *same model* with different system
prompts. You haven't created three specialists; you've created three conversations with one
model, at triple the cost, with information lost between them.

**A single agent prompted to research, then write, then critique does the same work with full
context throughout.** Often better.

> **Before building multi-agent, answer this:** what does the second agent's *separate context
> window* buy me that a well-structured single agent doesn't?
>
> If you can't answer in one sentence, build the single agent.

---

## 20.3 · When it genuinely helps

Three cases. They're narrower than the diagrams suggest, and they're real.

### 1 · Parallel fan-out over independent work

The strongest case. When a task decomposes into genuinely independent sub-tasks, running them
concurrently is a real win in wall-clock time.

```
"Compare how these 12 competitors handle refunds."

Single agent:   12 sequential research cycles. Context fills up. 6 minutes.
Multi-agent:    12 subagents in parallel, each returns a summary. 40 seconds.
```

**Requirements for this to work:** the sub-tasks must be genuinely independent (no sub-task needs
another's output), and the results must be summarisable into something small.

### 2 · Context isolation for reading-heavy work

**This is the underrated one, and it's the best justification for the pattern.**

Some sub-tasks involve consuming enormous amounts of material to produce a small conclusion.
Reading forty files to answer one question. Searching twelve sources to extract three facts.

Do that in the main agent's context and you've filled the window with material that was only
needed transiently — and section 5.11 says the important early instructions are now buried.

```
   Main agent context:        Subagent context:
   ┌──────────────────┐       ┌──────────────────┐
   │ task             │       │ "which of these  │
   │ plan             │       │  40 files use    │
   │ ...              │       │  the old API?"   │
   │ "3 files use it: │◀──────│  [40 files]      │
   │  a.py, b.py,c.py"│       │  [grep results]  │
   └──────────────────┘       │  [file contents] │
     small, focused           └──────────────────┘
                                discarded afterwards
```

**The subagent reads 80,000 tokens and returns 30.** The main agent's context stays clean. That's
a genuine architectural benefit no amount of single-agent prompting achieves.

> **This is the heuristic to remember:** delegate when a sub-task's *reading* would pollute the
> main context, and its *conclusion* is small. Reading-heavy, output-light.

### 3 · Genuinely different capabilities

Not different prompts — different *models*, tools, or permissions.

- A cheap fast model handling bulk extraction while an expensive one does judgment.
- An agent with write access to production, isolated behind an approval boundary, called by an
  agent that has none.
- A model with a capability the orchestrator's model lacks.

Here the separation is real, and it buys you something a single agent can't have.

---

## 20.4 · Patterns

### Orchestrator–workers

```
   orchestrator ──▶ decomposes into N tasks
        │
   ┌────┼────┬────┐
   w1   w2   w3   w4     run in parallel
   └────┴────┼────┘
        │
   orchestrator ──▶ synthesises
```

The most useful pattern by far, and the one that captures both case 1 and case 2. Workers are
often just copies of the same agent with different task prompts.

**Start with the orchestrator delegating to copies of itself.** Only introduce a genuinely
different worker — a cheaper model for bulk reading, say — when you've measured that you need
one.

### Handoff

One agent transfers the whole conversation to another and steps out.

```
   triage agent ──▶ "this is a billing question" ──▶ billing agent
```

Useful for routing into genuinely different domains with different tools and permissions. Much
simpler than it looks: it's a router (section 15.4) where the destinations happen to be agents.

**The catch:** the receiving agent inherits a context it didn't build. Be explicit about what
gets passed and what's summarised.

### Evaluator–optimiser

```
   generate ──▶ critique ──▶ revise ──▶ critique ──▶ ...
```

Genuinely helpful when there's an **objective** quality signal — tests that run, a schema that
validates, a linter. Much weaker when the critic is just the same model judging vibes, because
then you're relying on self-assessment, which section 17.6 warned you about.

**Ask: is the critic checking something real?** If yes, this pattern earns its cost. If no, you
have two model calls producing one opinion.

### Debate

Multiple agents argue; a judge decides. Interesting research, rarely worth the cost in
production. Know it exists.

---

## 20.5 · Communication is the hard part

If you build this, **most of your engineering effort goes here** — not into the agents.

### Structure the messages

```python
class SubTask(BaseModel):
    task_id: str
    objective: str = Field(description="What to accomplish, specific and self-contained.")
    context: str = Field(description="Everything the worker needs. Assume it knows nothing.")
    constraints: list[str]
    success_criteria: str = Field(description="How the worker knows it is done.")
    output_format: str


class SubResult(BaseModel):
    task_id: str
    status: Literal["completed", "partial", "failed"]
    findings: str
    sources: list[str]
    unresolved: list[str] = Field(description="What could not be determined, and why.")
    tokens_used: int
    cost_usd: float
```

Three fields doing real work:

**`context: "assume it knows nothing"`** — the direct defence against failure mode 1. Force
yourself to write down what the worker needs. You'll discover how much you were assuming.

**`unresolved`** — without it, a worker returns partial findings and the orchestrator treats them
as complete. This is the multi-agent version of silent truncation.

**`status: partial`** — because "completed" and "failed" aren't enough categories for real work.

### Budget every worker

```python
worker_limits = AgentLimits(
    max_iterations=6,
    max_cost_usd=0.15,
    max_duration_s=45,
)
```

Chapter 17's guards, per worker, **plus a global budget across all of them.** Without the global
cap, twelve workers each staying within budget can still produce an alarming total.

### Handle partial failure

```python
results = await asyncio.gather(*(run_worker(t) for t in tasks), return_exceptions=True)

succeeded = [r for r in results if isinstance(r, SubResult) and r.status != "failed"]
failed = [t for t, r in zip(tasks, results) if not isinstance(r, SubResult)]
```

Ten of twelve workers succeeding is usually a usable outcome — **if the orchestrator knows which
two failed.** Tell it explicitly, so the synthesis can caveat rather than silently omit.

---

## 20.6 · Failure modes

| Failure | Symptom | Fix |
|---|---|---|
| **Context loss** | Worker solves the wrong problem | Explicit, complete `context` in the task |
| **Duplicated work** | Two workers do the same thing | Non-overlapping decomposition; a shared task ledger |
| **Cost explosion** | 12 workers × 8 iterations | Per-worker *and* global budgets |
| **Silent partial results** | Synthesis omits what failed | `status` and `unresolved` fields, surfaced |
| **Orchestrator overload** | Its own context fills with results | Summarise worker output before synthesis |
| **Contradiction** | Two workers disagree | An explicit resolution rule; surface conflicts |
| **Cascading delay** | One slow worker blocks everything | Per-worker timeouts; proceed with what you have |
| **Untraceable errors** | Which agent was wrong? | Propagate a trace ID through every worker |

That last row is worth building for from day one. **One trace ID through the whole tree**, so you
can reconstruct a run. Retrofitting it is miserable.

---

## 20.7 · Build it

**An orchestrator–workers system**, with the honest comparison built in.

```
src/genai_toolkit/multiagent/
├── protocol.py      SubTask, SubResult
├── orchestrator.py  decompose · dispatch · synthesise
├── worker.py        a budgeted Chapter 17 agent
├── budget.py        per-worker and global caps
└── trace.py         one trace ID through the whole tree
```

Requirements:

1. **Decomposition** into independent, non-overlapping sub-tasks with explicit success criteria.
2. **Parallel execution** with bounded concurrency (`Semaphore` — Chapter 4).
3. **Per-worker and global budgets**, enforced.
4. **Partial failure handling** — the orchestrator is told what failed and caveats accordingly.
5. **Result summarisation** before synthesis, so the orchestrator's context stays clean.
6. **A single trace tree** rendering the whole run readably.
7. **A single-agent baseline implementation of the same task**, because of the comparison below.
8. `make check` green.

### The experiment that is the point of this chapter

**Take one realistic task. Implement it both ways. Run each 20 times.**

| | Single agent | Multi-agent |
|---|---|---|
| Success rate | | |
| Mean cost | | |
| Cost variance | | |
| p50 / p95 latency | | |
| Debugging time when it failed | | |

Then answer, in writing: **was it worth it, and why?**

Most of the time the honest answer is no — and being able to say that, with numbers, is worth
more in an interview than a multi-agent diagram. It demonstrates the judgment that section 20.0
is about.

Then find a task where the answer is **yes** — a reading-heavy fan-out is your best candidate —
and measure that too. Now you know where the line is, on your workload, rather than from a blog
post.

### Break it deliberately

1. Give a worker a task missing one crucial constraint. Watch it do good work on the wrong
   problem. **This is failure mode 1, and seeing it once is worth a chapter of reading.**
2. Decompose with deliberate overlap. Measure the wasted cost.
3. Make one worker hang. Confirm the timeout fires and synthesis proceeds.
4. Make half the workers fail. Confirm the final answer caveats honestly rather than pretending.
5. Have two workers reach contradictory conclusions. What does your orchestrator do? Make it say
   so explicitly.
6. Remove worker budgets and run a task that fans out to 20. Watch the cost. Then put them back.

---

## 20.8 · Exercises

**1 · The context-isolation win.** Build a task requiring reading 30 files to answer one
question. Measure main-context token usage with and without delegation. **This is the clearest
demonstration of the real benefit.**

**2 · Decomposition quality.** Take one complex task. Write three different decompositions. Run
each. Measure. Decomposition quality matters more than agent quality — show it.

**3 · Context-passing ablation.** Run the same workers with minimal, moderate and complete
`context` fields. Measure success rate at each. **Plot it.**

**4 · Cost model.** Derive a formula for multi-agent cost given N workers, mean iterations, and
context growth. Validate it against measurements.

**5 · Evaluator–optimiser, twice.** Implement it with an objective critic (tests must pass) and a
subjective one (model judges quality). Measure both against no critique. Report which earned its
cost.

**6 · Handoff routing.** Build triage → specialist handoff for three domains. Measure routing
accuracy and what's lost in the handoff.

**7 · Trace visualisation.** Render a multi-agent run as a readable tree with timing and cost per
node. Use it to debug a real failure.

**8 · The honest write-up.** Take your comparison table and write a one-page recommendation for
when *your* workload should and shouldn't use multiple agents. **Portfolio artefact.**

---

## 20.9 · Checkpoint

> **Move on to Chapter 21 when all of these are true.**

**Explain, out loud:**

1. The defining property of a multi-agent system. *(Separate context windows — not
   specialisation.)*
2. The five arguments against, with the one that bites most often.
3. Why "Researcher / Writer / Critic" is usually imaginary specialisation.
4. The three cases where it genuinely helps.
5. Why context isolation is the strongest of those three, with the reading-heavy heuristic.
6. Why communication design is where the engineering effort goes.
7. The one-sentence test before building multi-agent.

**Write from memory:**

8. `SubTask` and `SubResult`, including `unresolved` and `status`.
9. Bounded parallel dispatch with partial failure handling.
10. Per-worker and global budget enforcement.

**Verify:**

11. You have the single-agent versus multi-agent comparison table, from 20 runs each.
12. You can state, with numbers, when multi-agent is worth it for your workload.
13. You have demonstrated the context-isolation benefit with token counts.
14. You have watched a worker solve the wrong problem because of incomplete context.

Number 12 is the deliverable. **The skill this chapter teaches is knowing when not to.**

---

## 20.10 · Going deeper (optional)

**Re-read the multi-agent section of "Building Effective Agents."** It's deliberately cautious,
and having now built one you'll understand why.

**Read published post-mortems on multi-agent systems.** Several teams have written honestly about
what did and didn't work. The recurring theme is the one in section 20.2: coordination and
context-passing cost more than the parallelism saved.

**If you want the research:** look up work on agent communication protocols and on emergent
coordination failures. The academic framing of "why do these systems fail" is more rigorous than
the industry framing, and more useful.

**If you want the strongest counter-example:** look at how deep-research products fan out. The
pattern is exactly section 20.3's case 2 — many subagents reading enormous amounts and returning
compact summaries — and it works precisely because it plays to the real benefit.

---

<div align="center">

**[← Chapter 19](../ch19-mcp/)** · **[The Book](../../readme.md)** · **[Chapter 21 → Frameworks](../ch21-frameworks/)**

*Chapter 20 of 31 · Week 20*

</div>
