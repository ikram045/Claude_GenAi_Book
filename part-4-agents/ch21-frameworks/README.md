# Chapter 21 · Frameworks

### Now that you've built it by hand, you can judge what they're doing for you

> **Week 20, part 2 · ~11 hours**
>
> This chapter is last in Part IV on purpose. You have written the loop, the guards, the tool
> registry, the memory layer and the orchestrator. You are now the one person in the room who
> can evaluate a framework on the merits instead of on the README.

---

## 21.0 · Why this chapter is last

Chapter 1 named the Framework Trap:

> You learn the framework's abstractions instead of the underlying reality. Then it breaks —
> and it will — and you can't debug it, because you never understood what it was doing on your
> behalf.

That trap is only avoidable in one direction. Learn agents first, frameworks second, and a
framework becomes a tool you can evaluate, adopt on evidence, and abandon when it stops fitting.
Learn frameworks first and you have no basis for any of those three judgments.

You've done it in the right order. Now the question is a practical one: **for this project,
should I use a framework, and which?**

---

## 21.1 · What you actually built

Before comparing anything, inventory what your hand-rolled system does. This list *is* your
evaluation checklist, and it's better than any framework's feature matrix because it's derived
from problems you actually hit.

| Component | Chapter | Why it exists |
|---|:---:|---|
| The loop | 17 | Call, execute, feed back, repeat |
| Iteration cap | 17 | Infinite loops |
| Cost budget | 17 | Financial protection |
| Timeout | 17 | User-facing latency |
| Repetition detection | 17 | Same call, over and over |
| Progress detection | 17 | Oscillation — the subtle one |
| Circuit breaker | 17 | Everything failing |
| Every `stop_reason` handled | 17 | Silent truncation |
| Tool registry with schemas | 16 | Schema/implementation drift |
| Permission levels | 16 | Irreversible actions |
| Approval gating | 17 | Human in the loop |
| Context-based auth | 16 | Data exfiltration |
| Result truncation | 16 | Context blowout |
| Errors as results | 16 | Recovery instead of crash |
| Parallel execution | 16 | Latency |
| Working-memory management | 18 | Context exhaustion |
| Long-term memory | 18 | Cross-session continuity |
| Structured task state | 18 | Reliable step tracking |
| Trace rendering | 17 | Debuggability |
| Prompt caching | 9 | Cost |

Twenty items. When you evaluate a framework, ask which of these it gives you, which it makes
harder, and which it silently omits.

**Most frameworks cover rows 1 and 9 well, rows 2–8 partially, and leave rows 10–20 to you.**
That's worth knowing before you assume a framework means you're done.

---

## 21.2 · The landscape

Four categories, distinguished by two questions: **who supplies the harness** (the loop and
context management), and **who supplies the deployment** (the infrastructure it runs on).

### 1 · Raw SDK — the manual loop

What you built. You own the harness and the deployment.

**Use it when** you need control the helpers don't expose, you want no beta dependencies, or the
system is small enough that a framework is overhead.

**Cost:** twenty rows of the table above are yours to write and maintain.

### 2 · SDK tool runner — harness only

Most SDKs ship a helper that drives the loop for you, with tools defined as decorated typed
functions.

```python
from anthropic import beta_tool

@beta_tool
def get_weather(location: str, unit: str = "celsius") -> str:
    """Get current weather for a location.

    Args:
        location: City and state, e.g. San Francisco, CA.
        unit: Temperature unit, "celsius" or "fahrenheit".
    """
    return f"18°C and raining in {location}"


runner = client.beta.messages.tool_runner(
    model="claude-opus-5",
    max_tokens=16_000,
    tools=[get_weather],
    messages=[{"role": "user", "content": "What's the weather in London?"}],
)

for message in runner:
    print(message)
```

**What you get:** the loop, schemas generated from signatures and docstrings, automatic
termination. Per-turn hooks let you keep approval gates, error interception and result
modification.

**What you still own:** deployment, and most of rows 10–20.

**The gotcha to know about:** a long-running server-side tool can return `stop_reason:
"pause_turn"`, and some runners **do not resume automatically** — the loop exits and hands you a
silently truncated answer, no error, no warning. If you use server tools with a runner, mirror
the conversation as you iterate and restart the runner on a paused turn, with a cap on restarts.
This is exactly the kind of detail you can only evaluate because you know what `pause_turn` is.

### 3 · Managed agents — harness *and* deployment

The provider runs the agent loop **and** hosts a per-session container where tools execute. You
create a persisted, versioned agent configuration, then start sessions against it.

**What you get:** no loop code, no state files, no scheduler. A sandbox with bash, file
operations and code execution. Session budgets enforced by the platform. Scheduled runs.

**What you give up:** control over where compute happens, and portability.

**Use it when** you want a hosted, stateful, long-running or scheduled agent, and you'd rather
not operate one. It's often genuinely the *simplest* option despite being the biggest platform —
"simplest" means least code you own, and this is the only option that removes deployment.

### 4 · Agent frameworks — harness only, third-party

The largest category, and the one people mean by "agent framework."

**Graph-based orchestration** (LangGraph and similar) models your agent as a state machine:
nodes are steps, edges are transitions, state is explicit. Strong when your control flow is a
graph you can draw — which, from Chapter 17, is most *workflows*. Gives you persistence,
checkpointing, resumption and human-in-the-loop interrupts. The cost is a real abstraction to
learn and a lot of machinery for a simple loop.

**Batteries-included coding agents** (the Claude Agent SDK and its equivalents) ship a complete
harness *plus* built-in tools — file read/write/edit, bash, grep, web search — along with
permissions, hooks, subagents and sessions. You call `query(prompt, options)` and it drives
everything. Excellent when your agent's job is to work on a codebase or filesystem. Overkill
when it isn't.

> **The distinction that confuses everyone:** an SDK *tool runner* and an *agent SDK* sound
> alike and are different products. The tool runner is a thin helper over the messages endpoint
> that loops over **tools you define** — no built-in tools, no filesystem. An agent SDK is a
> full harness **with** built-in tools. Both leave deployment to you. Only managed agents add
> hosting.
>
> Getting this wrong means choosing the wrong tool for a month.

---

## 21.3 · Evaluating one

Run any candidate against this checklist. It's derived from your own code, which makes it
sharper than a feature comparison.

### Does it give you the guards?

- [ ] Iteration cap
- [ ] **Cost budget** — check carefully; many frameworks have none
- [ ] Timeout
- [ ] Repetition / oscillation detection
- [ ] Circuit breaker on repeated failures
- [ ] Every `stop_reason` handled, including `pause_turn` and `refusal`

### Can you keep your safety model?

- [ ] Permission levels per tool
- [ ] Human approval for irreversible actions, without hacking the internals
- [ ] Context-based auth — can you keep identity out of tool arguments?
- [ ] Rate limiting per session

### Can you see inside it?

- [ ] Is there a trace, and is it readable?
- [ ] Can you log the **exact prompt sent**? *(Section 15.5, failure mode 4. If you can't, you
      cannot debug three of the eight RAG failure modes.)*
- [ ] Are token counts and costs exposed per call?
- [ ] Can you intercept before and after each tool call?

### Operational reality

- [ ] Does it support **streaming**? Section 9.8 says this is your biggest perceived-quality
      lever, and some frameworks make it awkward.
- [ ] Does it support **prompt caching**, and does its prompt assembly keep the prefix stable?
      *(A framework that reorders tools per request destroys your cache and never tells you.)*
- [ ] Async-native, or bolted on?
- [ ] How many dependencies does it pull in?
- [ ] Is it maintained? Check commit frequency and issue response times, not the star count.

### The exit question

- [ ] **How much of my code would change if I removed this?**

If the answer is "everything," you've coupled your business logic to a framework, and that
framework's breaking changes are now your breaking changes.

---

## 21.4 · The abstraction tax

Every framework charges one. Know what you're paying.

**Debugging gets harder.** Something goes wrong six layers into someone else's abstraction.
Understanding it means reading their source anyway — the thing the framework was supposed to
save you from.

**You inherit their opinions.** How context is managed, how errors are handled, how prompts are
assembled. Some of those will be wrong for you, and changing them means fighting the framework.

**Hidden prompts.** Many frameworks inject their own text. You may not see it and may not be able
to change it. **Log the final prompt on your first day with any framework** — the surprise is
common and instructive.

**Cache invalidation.** Section 9.4: caching is a prefix match. If the framework rebuilds the
prompt with a non-deterministic tool ordering or injects a timestamp, your cache silently never
hits. Verify `cache_read_input_tokens` before you believe caching works.

**Version churn.** This field moves fast, and frameworks move faster. Breaking changes are
routine.

**Skill transfer.** Deep framework knowledge transfers poorly. Deep *agent* knowledge transfers
completely. You've built the transferable half; protect that ratio.

---

## 21.5 · When to adopt, when to stay raw

### Reach for a framework when

- **Your control flow is genuinely a graph** with branches, retries and resumption. This is
  where graph frameworks earn their keep.
- **You need persistence and resumption** across process restarts. Real machinery you'd
  otherwise build.
- **Your agent works on a codebase or filesystem** and a batteries-included SDK already has the
  tools.
- **You want the deployment gone** — that's managed agents.
- **Your team already uses it.** Consistency beats marginal technical fit.

### Stay raw when

- **The loop is simple** — one agent, a handful of tools. Chapter 17's loop is 100 lines you
  fully understand.
- **You need unusual control** — custom termination, unusual budgeting, a bespoke approval flow.
- **Latency is critical.** Abstraction layers cost milliseconds and sometimes extra model calls.
- **You're still learning the problem.** Frameworks encode decisions you're not ready to make.

### The recommendation

> **Start raw. Add a framework when you feel a specific pain it solves.**
>
> "This might scale better" is not a pain. "I have rewritten checkpoint-and-resume three times
> and it's still buggy" is.

And whichever you choose, **keep your business logic framework-free**. Your tools, your
retrieval, your permission model, your prompts — none of these should import the framework. The
framework orchestrates; it shouldn't own.

```python
# ✅ Portable: the framework calls this, but it doesn't depend on the framework
async def search_policies(query: str, ctx: RequestContext) -> SearchResult: ...

# ❌ Welded: you cannot move or test this without the framework
class SearchPoliciesNode(FrameworkNode):
    def run(self, state: FrameworkState) -> FrameworkState: ...
```

---

## 21.6 · Build it

**Port your Chapter 17 agent to a framework, and compare honestly.**

Requirements:

1. **Same task, same tools, same evaluation set** as your hand-rolled agent.
2. **Implement it in at least one framework** — a tool runner is the cheapest starting point; a
   graph framework is the most informative if your task branches.
3. **Run the checklist from 21.3** against it and fill it in, item by item.
4. **Measure both:** success rate, cost, p50/p95 latency, lines of code you maintain, and time to
   debug an injected failure.
5. **Verify prompt caching still works** in the framework version. Print
   `cache_read_input_tokens`.
6. **Log the exact prompt** the framework sends, and diff it against yours. Note anything
   injected you didn't write.
7. **Write a one-page recommendation:** would you ship this, and why?

### The comparison table

| | Hand-rolled | Framework |
|---|---|---|
| Lines of code I maintain | | |
| Guards from the 21.1 list, present | /20 | /20 |
| Success rate (20 runs) | | |
| Mean cost | | |
| p95 latency | | |
| Cache hit rate | | |
| Time to debug an injected bug | | |
| Can I log the exact prompt? | | |
| What would break if I removed it | | |

**That table is a portfolio artefact**, and the recommendation you write from it is an interview
answer that very few candidates can give — because very few have built both.

### Break it deliberately

1. Inject a bug deep in a tool. Time how long it takes to find under each implementation.
2. Make a tool hang. Does the framework time out, or hang with it?
3. Give it a task that loops forever. Does it stop? At what cost?
4. Add a timestamp to the system prompt. Does the framework's caching notice? Does yours?
5. Try to add a human approval gate for one tool. How hard is it in each?
6. Upgrade the framework a minor version. Does anything break?

---

## 21.7 · Exercises

**1 · The hidden-prompt audit.** Log the exact request a framework sends. Diff it against your
hand-built prompt. **Document every difference.** Most people have never looked.

**2 · Guard inventory.** Take the 21.1 list and mark, for one framework, which it provides, which
it makes possible, and which it prevents.

**3 · Exit cost.** Take your framework implementation and remove the framework. Time it. Count
the lines changed. **That number is your lock-in.**

**4 · Streaming check.** Implement token streaming in the framework version. Compare TTFT against
your hand-rolled version. Some frameworks add real latency here.

**5 · Cache verification.** Run 10 identical requests through the framework. Print
`cache_read_input_tokens` each time. If it's zero, find out why. *(This is the most common silent
framework cost.)*

**6 · Two frameworks.** Implement the same agent in two. The differences in what's easy and what's
awkward will teach you more about both than any documentation.

**7 · The wrong tool.** Deliberately use a heavy graph framework for a three-step linear
workflow. Feel the overhead. Then implement it as a plain function chain and compare.

**8 · Write the recommendation.** One page: what you'd use for this project, what you'd use for a
different one, and what would make you change your mind.

---

## 21.8 · Checkpoint

> **Move on to Project D when all of these are true.**

**Explain, out loud:**

1. The harness/deployment distinction, and which of the four categories supplies each.
2. The difference between an SDK tool runner and an agent SDK — and why confusing them is
   expensive.
3. Five components of the abstraction tax.
4. Why keeping business logic framework-free matters more than which framework you pick.
5. The exit question, and why you ask it before adopting.
6. Two concrete situations where a framework clearly wins, and two where raw clearly wins.
7. How a framework can silently destroy your prompt caching.

**Verify:**

8. You have implemented the same agent both ways.
9. You have filled in the 21.3 checklist for a real framework.
10. You have the comparison table with real measurements.
11. You have logged and diffed the exact prompts, and know what was injected.
12. You have a written recommendation you'd defend.

**And the meta-checkpoint:** you can now read a framework's source and understand what it's
doing, because you've written every piece of it. That's the position Chapter 1 was steering you
toward, and you're in it.

---

## 21.9 · Going deeper (optional)

**Read a framework's agent loop source.** Find the `while` loop. Compare it to yours. Note which
guards it has and which it doesn't. This is the single most clarifying hour available to you
right now.

**Read the changelogs** of two frameworks over the last year. Count the breaking changes. That's
the maintenance cost you're signing up for, quantified.

**If you're evaluating managed agents:** read the documentation on session budgets, environments,
and scheduled deployments. The value is in what you *don't* operate, so read the operations
section closely.

**If you want the long view:** this field's frameworks have a short half-life, and the durable
skill is understanding the loop, the guards, the tool boundary and the context economics. You
have that. Frameworks will keep changing; you'll keep being able to evaluate them.

---

<div align="center">

**[← Chapter 20](../ch20-multi-agent/)** · **[The Book](../../readme.md)** · **[Project D → Multi-Tool Agent](../project-d-multi-tool-agent/)**

*Chapter 21 of 31 · Week 20 · End of Part IV theory*

</div>
