# Chapter 26 · Deployment

### Shipping it, changing it safely, and being able to sleep

> **Week 25, part 2 · ~11 hours**
>
> The last chapter before you start applying. Everything you've built becomes something other
> people depend on.

---

## 26.0 · Why this chapter exists

Most of deployment is ordinary. Containers, configuration, health checks, horizontal scaling —
you know this from Flutter backends and from Project A.

Four things are genuinely different about LLM systems, and each has caught teams out:

**1 · Your prompts are configuration, and changing one is a deploy.** A prompt edit can change
behaviour more than a code change, and it has no type checker, no linter, and no compiler to
catch it. Yet people edit prompts in a web console and call it a tweak.

**2 · Your critical dependency is someone else's API**, with rate limits you don't control,
capacity you can't provision, and occasional incidents you can only wait out.

**3 · Cost is unbounded by default.** A loop, a caching regression, or a traffic spike can
multiply the bill overnight in a way a normal service simply can't.

**4 · "Working" is a distribution.** You can't smoke-test your way to confidence. Your eval suite
is your smoke test, and it has to run against the thing you're actually shipping.

This chapter is those four.

---

## 26.1 · The architecture

```
                   ┌──────────────┐
                   │ load balancer│
                   └──────┬───────┘
          ┌───────────────┼───────────────┐
     ┌────▼────┐    ┌─────▼───┐    ┌──────▼──┐
     │  API    │    │  API    │    │  API    │   stateless · scales horizontally
     └────┬────┘    └────┬────┘    └────┬────┘
          └──────────────┼──────────────┘
              ┌──────────┼──────────┬─────────────┐
         ┌────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌──────▼─────┐
         │ Postgres│ │ Redis  │ │ queue  │ │  provider  │
         │+pgvector│ │ cache  │ │        │ │   API      │
         └─────────┘ └────────┘ └───┬────┘ └────────────┘
                                ┌───▼────┐
                                │ workers│  ingestion · long agent runs · batch
                                └────────┘
```

Three principles:

**Keep the API stateless.** All state in Postgres and Redis. Then scaling is adding instances,
and a crash loses nothing.

**Separate workers from the API.** Ingestion, long agent runs and batch jobs don't belong in a
request handler. They take minutes, they should survive a restart, and they shouldn't compete
for the API's connection pool.

**Remember that workers are separate processes.** Section 4.14: they share no memory. Any
in-process cache exists separately in each one, which produces inconsistent results across
requests. Shared state goes in Redis.

---

## 26.2 · Prompts are config, and config needs rollout

The most important section in this chapter, because it's the thing that's genuinely different.

A prompt change can alter behaviour more than a refactor. It deserves the same rollout discipline
as a schema migration.

### Version, don't edit

From section 7.12: prompts live in files, with versions and changelogs. In deployment, add the
ability to **select a version at runtime**:

```python
class PromptConfig(BaseSettings):
    answer_prompt_version: str = "v4"
    rewrite_prompt_version: str = "v2"
    judge_prompt_version: str = "v3"
```

Now a prompt rollout is a config change you can stage and revert **without a code deploy** — and
crucially, **without a rebuild**, which means rollback is seconds rather than minutes.

### The staged rollout

```
  1 · EVAL      full suite on the new version. It must beat or match on every metric.
       │         Chapter 22's CI gate does this automatically on the PR.
  2 · SHADOW    run it on real traffic, log the output, serve the OLD version.
       │         Compare. Nobody is affected.
  3 · CANARY    serve to 5% of traffic. Watch quality proxies and cost.
       │
  4 · RAMP      25% → 50% → 100%, watching at each step.
       │
  5 · CLEAN     remove the old version after a soak period.
```

**Shadow mode is the underused one**, and it's the most valuable for prompts specifically:

```python
async def answer(q: str, ctx) -> Answer:
    result = await generate(q, version=settings.answer_prompt_version)

    if settings.shadow_version:
        asyncio.create_task(shadow_compare(q, ctx, settings.shadow_version, result))

    return result
```

You get real-traffic comparison with zero user risk. For a change whose eval score is close, this
is how you decide.

### Kill switches

```python
class FeatureFlags(BaseSettings):
    reranking_enabled: bool = True
    agent_enabled: bool = True
    semantic_cache_enabled: bool = True
    max_agent_iterations: int = 15
    monthly_budget_usd: float = 5000
```

**Every expensive or risky feature gets a flag you can flip without deploying.** When the
reranker provider has an incident at midnight, you want to turn it off in ten seconds, not ship a
release.

---

## 26.3 · Living with a provider you don't control

### Know your limits, and watch them

Rate limits are usually per-minute on requests *and* tokens. Track how close you are:

```python
metrics.gauge("provider.rate_limit_utilisation",
              current_rpm / limit_rpm, tags={"model": model})
```

Alert at 80%. Hitting a limit is not an emergency if you knew it was coming.

### Design for their incidents

Providers have outages. Your options, in order of effort:

| Strategy | Notes |
|---|---|
| **Retry with backoff** | The SDK does this. Configure it (section 6.5) |
| **Fall back to another model** | Works. **Different cache namespace** — expect a cost spike |
| **Fall back to another provider** | Real work: different SDK, different prompt behaviour, different eval numbers |
| **Degrade to no generation** | Section 25.5's sources-only tier. Cheap and often enough |
| **Queue and retry later** | For anything asynchronous |

**Decide which of these you're doing before the incident**, and write it in the runbook. Deciding
during is how bad decisions get made.

### The idempotency problem

If a request times out, did it succeed? You were billed either way. For anything with side
effects, use idempotency keys so a retry doesn't send the email twice.

---

## 26.4 · Configuration and secrets

Chapter 3's `pydantic-settings`, at production scale.

**Validate at startup, and fail fast.** A misconfigured service should refuse to start with a
clear message, not serve broken responses.

```python
@app.on_event("startup")
async def validate_config() -> None:
    settings = get_settings()
    await check_db_connection()
    await check_vector_index_exists()
    await check_model_reachable()          # one cheap call
    check_prompt_versions_exist(settings)  # ← catches a typo'd version name
    logger.info("startup checks passed: model=%s prompts=%s",
                settings.model, settings.prompt_versions)
```

That last check has saved people a bad morning: a config referencing `v5` when only `v4` exists
should fail at startup, not on the first user request.

**Secrets from a secret manager**, not environment variables in a compose file. Rotate on a
schedule. Never log a settings object (section 3.9).

---

## 26.5 · Health checks that mean something

```python
@app.get("/health/live")
async def live() -> dict:
    return {"status": "ok"}          # is the process alive?


@app.get("/health/ready")
async def ready() -> dict:
    checks = {
        "database": await check_db(),
        "vector_index": await check_index(),
        "cache": await check_redis(),
        "provider": await check_provider_reachable(),
    }
    if not all(checks.values()):
        raise HTTPException(503, detail=checks)
    return {"status": "ready", "checks": checks}
```

**Liveness and readiness are different questions.** Liveness: should this process be restarted?
Readiness: should it receive traffic? Conflating them causes restart loops when a dependency is
briefly down — the process is fine, it just isn't ready.

And from section 4.15: **`/health` must stay responsive while a long generation is running.** If
it stalls, you're blocking the event loop, and your orchestrator will start killing healthy
processes.

---

## 26.6 · The launch checklist

Work through it literally.

### Correctness
- [ ] Eval suite passes on the exact config being shipped
- [ ] Eval runs in CI and blocks merges on regression
- [ ] Red-team suite (section 24.7) green
- [ ] Canary eval scheduled against production

### Safety
- [ ] No tool takes an identity from its arguments
- [ ] Irreversible actions gated on human approval
- [ ] Output filtering: domain allowlist, PII, markdown images
- [ ] Rate limits per user and per session
- [ ] Threat model written; trifecta audit done

### Cost
- [ ] Monthly budget set, with a decided behaviour at 100%
- [ ] Per-user quotas
- [ ] Budget alert at 80% of projection
- [ ] Cost per request known, and its p99
- [ ] Cache hit rates monitored, with an alert on collapse

### Reliability
- [ ] Timeouts at every layer, with a bounded total
- [ ] Bounded concurrency on every outbound call
- [ ] Backpressure — rejects fast under overload
- [ ] Degradation chain tested by killing each dependency
- [ ] Retries with jittered backoff; idempotency for side effects

### Observability
- [ ] Traces on every request, with the exact assembled prompt
- [ ] Request ID returned to the client
- [ ] All the section 23.6 metrics, with percentiles
- [ ] Alerts on rolling baselines, both refusal directions
- [ ] Feedback collection wired to a triage queue

### Operations
- [ ] Liveness and readiness separated; startup validation fails fast
- [ ] Kill switches for every expensive feature
- [ ] Prompt versions selectable at runtime
- [ ] Rollback tested — **actually performed once**
- [ ] Runbook written
- [ ] Secrets in a manager, rotation scheduled

### Data
- [ ] PII redacted before traces, logs and memory
- [ ] Retention policy set and enforced
- [ ] Deletion removes rows, vectors, traces and memories
- [ ] Multi-tenant scoping verified with a test

---

## 26.7 · The runbook

Write it before you need it. Someone tired at 3am — possibly you — will follow it.

```markdown
# Runbook — Document Assistant

## Quick reference
Dashboard · Traces · Logs · Provider status page
Kill switches: `ENABLE_RERANKING`, `ENABLE_AGENT`, `MONTHLY_BUDGET_USD`

## Cost has spiked
1. `cost by route, last 6h` — which route?
2. Check cache hit rate. A collapse is the most common cause.
   → Look for a timestamp or UUID in the system prompt (§9.4).
3. Check agent iteration distribution. Runs hitting the cap?
   → Lower `MAX_AGENT_ITERATIONS`.
4. Check for one heavy user. → Apply a quota.
5. If unclear and severe: set `MONTHLY_BUDGET_USD` to force degradation, then
   investigate. Cost is reversible; a surprise invoice is less so.

## Quality complaints
1. Get the request ID. If they don't have it, get the session and time.
2. Open the trace. Was the answer in the retrieved context?
   → NO: retrieval problem. Check the assembled prompt (§15.5, modes 1–4).
   → YES: generation problem (§15.5, modes 5–8).
3. Add it as an eval case (`make trace-to-eval TRACE=...`).
4. Fix, confirm the eval passes, ship.

## Provider incident
1. Check their status page.
2. Confirm with the error class in our metrics.
3. If sustained > 10 min: set `FALLBACK_MODEL`. Expect a cost increase —
   different cache namespace.
4. If both unavailable: `ENABLE_GENERATION=false` → sources-only mode.
5. Post in #incidents with the expected user impact.

## Latency alert
1. Is it us or them? Compare our stage timings against provider TTFT.
2. Ours: check retrieval and reranker timings; check DB connections.
3. Theirs: consider lowering `effort` temporarily.

## Rolling back a prompt
`ANSWER_PROMPT_VERSION=v3` and restart. No rebuild. ~30 seconds.
```

**Two properties of a good runbook:** every step is a command or a link, and every branch ends in
an action. "Investigate further" is not a step.

---

## 26.8 · Build it

**Deploy Project C or D properly.** This is Project E, and this chapter is its specification.

Requirements:

1. **Containerised** — multi-stage build, non-root, health checks (Project A's Dockerfile).
2. **Stateless API + workers**, with a queue between them.
3. **Postgres + pgvector + Redis**, via compose.
4. **Startup validation** that fails fast on bad config, including prompt versions.
5. **Liveness and readiness separated**, with `/health/live` responsive under load.
6. **Runtime-selectable prompt versions** and kill switches.
7. **Shadow mode** for at least one prompt.
8. **Eval in CI**, blocking regressions.
9. **A canary** running against production.
10. **A runbook**, following section 26.7.
11. **Rollback performed at least once**, and timed.
12. `make check` green.

### The drills

Do these deliberately. Each one is something that will happen.

1. **Roll back a prompt under load.** Time it. Under 60 seconds?
2. **Kill the vector store.** Does it degrade or error? Is it recorded?
3. **Rate-limit yourself.** Exhaust your quota deliberately. Watch the fallback.
4. **Break the cache.** Add a timestamp. Watch cost triple and the alert fire.
5. **Deploy a bad prompt.** Confirm CI catches it before it ships.
6. **Overload it.** Ramp until backpressure engages. Confirm it rejects rather than collapses.
7. **Follow your own runbook**, cold, for a problem you didn't cause. Fix every step that was
   unclear.

That last one is the real test. **A runbook you haven't followed is a document, not a runbook.**

---

## 26.9 · Checkpoint

> **Move on to Project E when all of these are true.**

**Explain, out loud:**

1. Four ways deploying an LLM system differs from deploying a normal service.
2. Why a prompt change deserves a staged rollout, and what shadow mode gives you.
3. Why liveness and readiness are different questions.
4. Why worker processes sharing no memory breaks in-process caches.
5. Your plan for a provider outage, decided in advance.
6. Why rollback must not require a rebuild.

**Verify:**

7. `docker compose up` from a clean clone gives a working system.
8. Startup validation fails fast on a bad prompt version.
9. `/health/live` stays responsive during a long generation.
10. You have rolled back a prompt version and timed it.
11. Every kill switch has been flipped at least once.
12. You have followed your own runbook for a problem you didn't cause.
13. Every box in section 26.6 is ticked.

---

## 26.10 · Going deeper (optional)

**Read about progressive delivery** — canaries, feature flags, shadow traffic. Standard practice
in web engineering and unusually well-suited to prompt changes, because prompt effects are
statistical and need real traffic to see.

**Read SRE material on error budgets.** The framing — how much unreliability is acceptable, and
what you do when you've spent it — maps well onto quality budgets for probabilistic systems.

**If you want the incident-response angle:** read a few published post-mortems and note the
structure. Writing one for your own drill is excellent practice and an unusual portfolio piece.

---

<div align="center">

**[← Chapter 25](../ch25-performance-and-cost/)** · **[The Book](../../readme.md)** · **[Project E → To Production](../project-e-to-production/)**

*Chapter 26 of 31 · Week 25 · End of Part V theory*

</div>
