# Chapter 17 · The Agent Loop

### Twelve lines that work, a hundred that ship, and knowing when not to use one at all

> **Week 17 · ~22 hours · Heavy code**
>
> You write this by hand. No frameworks — those are Chapter 21, deliberately last. By the end
> of this week you'll understand exactly what every agent framework is doing on your behalf,
> which is the only position from which you can judge one.

---

## 17.0 · Why this chapter exists

The agent loop is genuinely simple. Here it is:

```python
while True:
    response = call_model(messages, tools)
    if response.stop_reason == "end_turn":
        return response
    messages.append({"role": "assistant", "content": response.content})
    results = execute_tools(response)
    messages.append({"role": "user", "content": results})
```

Twelve lines. That's an agent — a model in a loop with tools, deciding its own next step.

And that loop, shipped as written, will one day run for four hundred iterations, call the same
failing tool two hundred times, exhaust your context window, spend $340, and return nothing.
Every production agent is those twelve lines plus a hundred more that stop it doing that.

This chapter is the hundred lines. It's also, more importantly, about **when not to write a
loop at all** — because the most common mistake in this entire field is reaching for an agent
where a fixed pipeline would have been better, cheaper, and more reliable.

---

## 17.1 · Agents and workflows

> **Workflow:** you decide the steps. The model fills them in.
> **Agent:** the model decides the steps. You set the boundaries.

```
WORKFLOW                              AGENT

  extract ──▶ classify ──▶ summarise    ┌──▶ model decides
    │           │            │          │        │
    └───────────┴────────────┘          │    tool call
   You wrote this control flow.         │        │
   It runs the same way every time.     └──── result
                                          (until it decides to stop)
```

Both are legitimate. They have very different properties:

| | Workflow | Agent |
|---|---|---|
| Predictability | High — same path every time | Low — different path per run |
| Debuggability | Easy — you know where it is | Hard — where did it go? |
| Cost | Predictable | Variable, occasionally alarming |
| Latency | Predictable | Variable |
| Handles novelty | Only what you anticipated | Adapts |
| Testing | Standard | Statistical |

### The rule

> **Use the simplest thing that works.** A single model call beats a workflow. A workflow beats
> an agent. Reach for an agent only when the task genuinely cannot be specified in advance.

Four questions before you write a loop:

1. **Complexity** — is the task multi-step *and* hard to fully specify ahead of time? "Turn this
   design doc into a PR" qualifies. "Extract the title from this PDF" does not.
2. **Value** — does the outcome justify higher cost and latency?
3. **Viability** — is the model actually capable at this task?
4. **Cost of error** — can mistakes be caught and recovered? Is there a test, a review, a
   rollback?

**If any answer is no, build a workflow.**

### Workflow patterns worth knowing first

Most tasks people build agents for are actually one of these:

**Chaining** — fixed sequence, each step's output feeding the next. Section 7.11.
**Routing** — classify the input, send it down one of several fixed paths. Section 15.4.
**Parallelisation** — run independent steps concurrently, combine results. `asyncio.gather`.
**Orchestrator–workers** — one call plans subtasks, workers execute them, one call combines.
**Evaluator–optimiser** — generate, critique, revise, with a fixed number of rounds.

Every one of these is deterministic control flow you can read, test and debug. They cover the
large majority of "agentic" use cases, and they do it with a fraction of the failure surface.

---

## 17.2 · The loop, properly

Now the real thing. Each addition exists because of a specific failure.

```python
from dataclasses import dataclass, field
import time


@dataclass
class AgentLimits:
    max_iterations: int = 15
    max_tokens_total: int = 150_000
    max_cost_usd: float = 1.00
    max_duration_s: float = 120.0
    max_consecutive_errors: int = 3
    max_repeated_calls: int = 3
    max_pause_restarts: int = 5


@dataclass
class AgentRun:
    messages: list[dict]
    iterations: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    consecutive_errors: int = 0
    call_signatures: dict[str, int] = field(default_factory=dict)
    stop_reason: str | None = None
    trace: list[dict] = field(default_factory=list)


async def run_agent(
    task: str,
    tools: ToolRegistry,
    limits: AgentLimits = AgentLimits(),
    ctx: RequestContext | None = None,
) -> AgentRun:
    run = AgentRun(messages=[{"role": "user", "content": task}])

    while True:
        # ---- guards, checked BEFORE spending money -----------------------
        if run.iterations >= limits.max_iterations:
            run.stop_reason = "max_iterations"
            break
        if run.total_cost >= limits.max_cost_usd:
            run.stop_reason = "budget_exhausted"
            break
        if time.perf_counter() - run.started_at > limits.max_duration_s:
            run.stop_reason = "timeout"
            break
        if run.total_tokens >= limits.max_tokens_total:
            run.stop_reason = "context_exhausted"
            break

        run.iterations += 1

        # ---- call the model ----------------------------------------------
        try:
            response = await call_model(
                messages=run.messages, tools=tools.schemas(), system=AGENT_SYSTEM
            )
        except RateLimitError:
            await asyncio.sleep(backoff(run.iterations))
            continue

        run.total_cost += cost_of(response.usage)
        run.total_tokens += response.usage.input_tokens + response.usage.output_tokens

        # ---- server-side tool paused mid-turn ----------------------------
        if response.stop_reason == "pause_turn":
            run.messages.append({"role": "assistant", "content": response.content})
            continue

        # ---- the model is finished ---------------------------------------
        if response.stop_reason == "end_turn":
            run.messages.append({"role": "assistant", "content": response.content})
            run.stop_reason = "completed"
            break

        if response.stop_reason == "refusal":
            run.stop_reason = "refused"
            break

        if response.stop_reason == "max_tokens":
            run.stop_reason = "truncated"
            break

        # ---- execute the requested tools ---------------------------------
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        run.messages.append({"role": "assistant", "content": response.content})

        # loop detection: is it asking for the same thing again?
        for block in tool_uses:
            sig = signature(block.name, block.input)
            run.call_signatures[sig] = run.call_signatures.get(sig, 0) + 1
            if run.call_signatures[sig] > limits.max_repeated_calls:
                run.stop_reason = "repeated_call_loop"

        if run.stop_reason:
            break

        results = await execute_all(tool_uses, tools, ctx, run.trace)

        # circuit breaker: everything is failing, stop burning money
        if all(r.is_error for r in results):
            run.consecutive_errors += 1
            if run.consecutive_errors >= limits.max_consecutive_errors:
                run.stop_reason = "repeated_tool_failures"
                break
        else:
            run.consecutive_errors = 0

        # ALL results in ONE user message (section 16.6)
        run.messages.append({
            "role": "user",
            "content": [r.to_block() for r in results],
        })

    return run
```

Read that against the twelve-line version. Nothing clever was added — just the specific answer
to each way the simple loop fails.

---

## 17.3 · Termination is the hard part

An agent that doesn't know when to stop is not an agent; it's a bill.

### The six stopping conditions

| Condition | Why |
|---|---|
| **`end_turn`** | The normal, happy case |
| **Iteration cap** | The universal backstop. Always set one |
| **Cost budget** | The one that protects you financially |
| **Wall-clock timeout** | The one that protects your users |
| **Token budget** | Before the context window ends the run for you, messily |
| **No-progress detection** | The subtle one — see below |

### Detecting no progress

The nastiest loop isn't the one calling the same tool identically — that's easy to catch with a
signature counter. It's the one *oscillating*:

```
iter 4  search("refund policy enterprise")      → nothing useful
iter 5  search("enterprise refund terms")       → nothing useful
iter 6  search("refund policy for enterprise")  → nothing useful
iter 7  search("enterprise customer refunds")   → nothing useful
```

Four different calls, four different signatures, zero progress. Signature counting won't catch
it.

Three detectors that will:

**1 · Result similarity.** If consecutive tool results are near-identical, the agent is
circling. Hash them, or compare embeddings.

**2 · Novel-information tracking.** Count distinct documents, IDs or facts seen. If three
iterations add nothing new, stop.

**3 · Ask the model.** Every N iterations, insert a checkpoint: *"You have made 6 tool calls.
Are you making progress toward the task? If not, say so and stop."* Cheap, and surprisingly
effective — the model is often well aware it's stuck.

### Give the loop an explicit exit

Make stopping a first-class action rather than something the model has to infer:

```python
@tool
def finish(answer: str, confidence: Literal["high", "medium", "low"]) -> str:
    """Call this when you have completed the task. Provide your final answer."""

@tool
def give_up(reason: str, what_was_tried: str) -> str:
    """Call this if the task cannot be completed with the available tools."""
```

`give_up` is the section 7.10 escape hatch, in tool form. Without it, an agent that cannot
succeed will keep trying, because trying is the only action available to it. With it, failure
becomes a clean, loggable outcome — and the `what_was_tried` field is genuinely useful
diagnostic data.

---

## 17.4 · How agent loops fail

A diagnostic catalogue, in the style of section 15.5.

### 1 · The infinite loop
**Symptom:** Same tool, same arguments, forever.
**Cause:** Tool returns nothing useful; the model retries identically.
**Fix:** Signature counting; better tool error messages that suggest alternatives.

### 2 · Oscillation
**Symptom:** Rephrasing the same failing query indefinitely.
**Cause:** The information isn't available; the model doesn't conclude that.
**Fix:** Progress detection; a `give_up` tool; a checkpoint prompt.

### 3 · Premature stop
**Symptom:** Answers after one tool call when three were needed.
**Cause:** The task's completion criteria were never stated.
**Fix:** Say what "done" means in the system prompt. *"Before finishing, confirm you have
checked both the policy and the exceptions document."*

### 4 · Context exhaustion
**Symptom:** Works for ten iterations, then degrades or errors.
**Cause:** Every iteration appends messages and tool results. Long runs overflow.
**Fix:** Chapter 18 — summarisation, tool-result trimming, compaction.

### 5 · Confabulated tool results
**Symptom:** The model writes what a tool "returned" without calling it.
**Cause:** More common with thinking disabled; also happens when a tool is described but
unavailable.
**Fix:** Never trust narrative — only act on actual `tool_use` blocks. Keep adaptive thinking
on. **Verify against your audit log** (16.10), not against the model's prose.

### 6 · Cost explosion
**Symptom:** One run costs 50× the average.
**Cause:** History grows every iteration, so token cost per iteration grows too. A 20-iteration
run is far more than 20× a single call.
**Fix:** Hard budget cap, checked before each call. Cache the stable prefix (9.4).

### 7 · Destructive action
**Symptom:** The agent does something irreversible and wrong.
**Cause:** No confirmation gate.
**Fix:** Section 16.4's permission levels. **This is the one that ends careers**, so treat it as
non-negotiable.

### 8 · Silent truncation
**Symptom:** A plausible but incomplete answer, no error anywhere.
**Cause:** `stop_reason` was `max_tokens` or `pause_turn` and you didn't check.
**Fix:** Branch on every `stop_reason` value explicitly. The loop in 17.2 does.

---

## 17.5 · Human in the loop

For anything consequential, a person approves before the action.

```python
async def execute_with_approval(
    block, tools: ToolRegistry, ctx: RequestContext
) -> ToolResult:
    tool = tools.get(block.name)

    if tool.permission is Permission.IRREVERSIBLE:
        decision = await request_approval(
            tool=block.name, args=block.input,
            summary=tool.describe_action(block.input),
            ctx=ctx,
        )
        if not decision.approved:
            return ToolResult(
                content=f"The user declined this action. Reason: {decision.reason}. "
                        f"Do not retry it. Consider an alternative or ask the user.",
                is_error=False,          # ← not an error. A decision.
            )

    return await tool.execute(block.input, ctx)
```

Two details that matter more than they look:

**A refusal is not an error.** Mark it `is_error=False` and phrase it as information. The model
should treat it as a legitimate outcome and adapt, not as a transient failure to retry.

**"Do not retry it."** Without this, a well-meaning agent will try again, and your user gets the
same approval dialog four times.

### Where to put the gate

| Placement | Tradeoff |
|---|---|
| Per action | Safest, most annoying |
| Per session ("allow sends for this task") | Good balance |
| Per action type, remembered | Convenient; make it revocable |
| Plan approval up front | Excellent for multi-step tasks — approve the whole plan, then run |

That last one deserves attention: having the agent produce a plan, showing it to the user, and
executing only after approval gives you most of the safety of per-action gating with almost none
of the friction.

---

## 17.6 · Planning and reflection

### Plan first

For multi-step tasks, have the agent state a plan before acting:

```
Before using any tools, write a brief plan:
1. What information you need
2. Which tools you'll use, in what order
3. How you'll know when the task is complete

Then execute it, adjusting if what you learn changes the picture.
```

Three benefits: the model reasons before acting (section 5.9); you can show the plan to a human
for approval; and when the run goes wrong, the plan tells you *where* it diverged.

### Reflect at the end

```
Before calling finish, check:
- Did you answer everything that was asked?
- Is every claim supported by a tool result?
- Is anything you're about to say not backed by evidence you gathered?
```

Catches premature stops and unsupported claims. Costs one extra model call.

**And note what it can't do:** the model checking its own work is subject to the same failure
modes as the work. Self-reflection is a useful filter, not a verifier. **Real verification is
external** — a test that runs, a schema that validates, a string that must appear in a source
document. Prefer those where you can get them.

---

## 17.7 · Observability

You cannot debug what you cannot see, and an agent run is much harder to see than a single call.

```python
@dataclass
class TraceEvent:
    iteration: int
    timestamp: float
    kind: str              # "model_call" | "tool_call" | "approval" | "guard_triggered"
    detail: dict
    duration_ms: float
    cost_usd: float
```

Record, for every run:

- Every model call: input tokens, output tokens, cost, latency, `stop_reason`
- Every tool call: name, arguments, result size, duration, error status
- Every guard that fired, and why
- The final outcome and total cost

And make it **readable**:

```
Run 7a3f · task: "find our refund policy for annual enterprise contracts"

  1  model    1,240 in ·   180 out · 0.9s · $0.011 · tool_use
     tool     search_policies(query="enterprise refund policy") · 340ms · 5 results
  2  model    3,180 in ·   210 out · 1.1s · $0.021 · tool_use
     tool     search_policies(query="annual contract exceptions") · 290ms · 3 results
  3  model    5,020 in ·   890 out · 3.2s · $0.047 · end_turn

  completed · 3 iterations · 8.4s · $0.079
```

**Print this during development. Every run.** You will spot the repeated call, the pointless
iteration, the tool returning nothing — things that are invisible in aggregate metrics and
obvious in a trace. Chapter 23 makes this production-grade.

---

## 17.8 · Cost control

Agent economics are worse than they look, and the reason is worth internalising.

```
Iteration 1:  1,000 input tokens
Iteration 2:  1,000 + result + response  ≈ 2,400
Iteration 3:                             ≈ 4,100
...
Iteration 10:                            ≈ 18,000

Total input for a 10-iteration run ≈ 85,000 tokens — not 10,000.
```

**Input tokens grow with every iteration, so total cost grows roughly quadratically with run
length.** A 20-iteration run isn't twice a 10-iteration run; it's closer to four times.

Five levers:

1. **Cache the stable prefix.** System prompt and tool definitions are identical every
   iteration — a textbook caching case (9.4).
2. **Cap iterations aggressively.** Start at 10. Raise it only when you measure that runs
   genuinely need more.
3. **Trim tool results.** The biggest thing in the context, and usually the most trimmable.
4. **Route by difficulty.** Simple tasks don't need an agent at all. Section 15.4.
5. **Use a cheaper model for sub-tasks.** Careful — caches are model-scoped, so measure whether
   the saving survives (section 9.6).

> **Judge cost per completed task, not per call** (section 9.7). A cheaper model that takes
> twelve iterations instead of four is more expensive, slower, and more likely to fail.

---

## 17.9 · Build it

**An agent loop**, hand-written, with every guard.

```
src/genai_toolkit/agent/
├── loop.py          run_agent, the full loop
├── limits.py        AgentLimits, guard evaluation
├── progress.py      repetition, oscillation and no-progress detection
├── approval.py      human-in-the-loop gating
├── trace.py         TraceEvent, the readable trace renderer
└── prompts/         versioned agent system prompts (Chapter 7's library)
```

Requirements:

1. **All six termination conditions**, checked before spending money.
2. **`finish` and `give_up` tools**, so stopping is an explicit action.
3. **Loop detection** — signature counting *and* at least one no-progress detector.
4. **Circuit breaker** on consecutive tool failures.
5. **Every `stop_reason` handled**, including `pause_turn` and `refusal`.
6. **Approval gating** for irreversible tools, with refusals returned as non-error results.
7. **A readable trace** printed per run, and stored as structured events.
8. **Prompt caching** on the stable prefix, with the hit rate visible in the trace.
9. **Tested against a fake client** that can be scripted to loop, oscillate, fail repeatedly,
   pause, and refuse.
10. `make check` green.

### Then break it deliberately

Each of these should trip a guard, not run away:

1. **A tool that always returns "no results."** Watch the agent loop. Confirm the signature
   counter stops it. Then improve the tool's error message and watch the behaviour change.
2. **A tool whose results are useless but varied.** Confirm your oscillation detector catches
   what signature counting misses. **This is the hard one.**
3. **A task needing 50 iterations.** Confirm it stops at your cap with a clear reason rather
   than running.
4. **An expensive task.** Confirm the budget guard fires before the money is gone.
5. **A tool that raises every time.** Confirm the circuit breaker fires after N.
6. **An impossible task.** Does the agent call `give_up`, or does it grind? If it grinds, your
   system prompt hasn't made giving up legitimate.
7. **A destructive tool with approval on.** Decline it. Confirm the agent adapts rather than
   retrying.
8. **Run one 20-iteration task and read the full trace.** Count how many iterations did
   anything useful. It's usually fewer than you'd guess, and that observation is what makes you
   a better agent designer.

---

## 17.10 · Exercises

**1 · The twelve-line version.** Write it. Give it a tool that always fails. Watch it loop
forever. **Feel the problem before you build the solution.**

**2 · Guard ablation.** Remove each guard in turn and find a task that breaks without it.
Document which guard catches which failure. *(This is your Chapter 21 framework-evaluation
checklist.)*

**3 · Oscillation detector.** Implement all three approaches from section 17.3. Compare them on
20 runs. Which catches the most? What are the false positives?

**4 · Workflow versus agent.** Take one multi-step task. Implement it both ways. Measure
success rate, cost, latency and variance over 20 runs. **The variance number is the interesting
one.**

**5 · Iteration economics.** Plot total cost against iteration count for a real task. Confirm
the curve is superlinear. Then add prompt caching and plot again.

**6 · Plan approval.** Implement plan-first execution with human approval of the plan. Compare
user friction against per-action approval on a 6-step task.

**7 · Completion criteria.** Find a task where the agent stops early. Fix it by stating
completion criteria in the system prompt. Measure the before/after success rate.

**8 · Trace reader.** Build the renderer from section 17.7. Use it on ten real runs. **Write
down three things you learned that aggregate metrics wouldn't have told you.**

---

## 17.11 · Checkpoint

> **Move on to Chapter 18 when all of these are true.**

**Explain, out loud:**

1. The difference between a workflow and an agent, and the four questions that decide.
2. Why the twelve-line loop is dangerous in production.
3. All six termination conditions and what each protects.
4. Why oscillation is harder to detect than repetition, and three ways to catch it.
5. Why agent cost grows superlinearly with iterations.
6. Why a declined approval must be a result rather than an error.
7. Why self-reflection is a filter and not a verifier.

**Write from memory:**

8. The full loop with all guards, handling every `stop_reason`.
9. A `give_up` tool and the system-prompt language that makes using it legitimate.
10. A no-progress detector.
11. Approval gating that returns a non-error refusal.

**Verify:**

12. Every guard has been triggered deliberately at least once.
13. Your trace renderer output is readable enough to debug from.
14. An impossible task terminates cleanly with a reason, not a timeout.
15. **You have read a full 20-iteration trace and can say how many iterations were wasted.**

Number 15 is the one that changes how you design agents.

---

## 17.12 · Going deeper (optional)

**Re-read "Building Effective Agents."** You read it in Chapter 1 and understood some of it.
Read it now and notice how much has become obvious — particularly the argument that most
"agentic" use cases are better served by workflows. That argument is the most valuable thing in
this chapter and it comes from there.

**Read about ReAct.** The reason-then-act pattern that underlies most agent loops. The original
paper is short and it will make the loop feel less arbitrary.

**Read your SDK's tool-runner implementation.** You've now written the loop by hand, so you can
read theirs critically: which of your guards does it have? Which does it leave to you?
**That's exactly the Chapter 21 question**, and you're now equipped to answer it.

**If you want the research frontier:** look up reflection and self-correction papers, and read
the critiques alongside them. The gap between "the model can critique its own output" and "the
model reliably improves its own output" is where a lot of agent hype lives.

---

<div align="center">

**[← Chapter 16](../ch16-tool-use/)** · **[The Book](../../readme.md)** · **[Chapter 18 → Memory & State](../ch18-memory-and-state/)**

*Chapter 17 of 31 · Week 17*

</div>
