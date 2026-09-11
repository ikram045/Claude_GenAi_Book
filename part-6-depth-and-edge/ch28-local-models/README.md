# Chapter 28 · Local & Open Models

### Running inference yourself — the arithmetic that decides whether you should

> **Week 28, part 1 · ~11 hours**
>
> The foundation for Chapter 30. Self-hosting is a real engineering discipline with a clear
> break-even calculation, and most people get the calculation wrong in both directions.

---

## 28.0 · Why this chapter exists

Two failure modes, equally common.

**Self-hosting because it feels cheaper.** You rent a GPU, discover it costs more per hour than
your entire API bill, and that you now own capacity planning, scaling and on-call for an
inference service.

**Never considering it**, and then being unable to build anything that must run offline, on a
device, or on data that cannot leave the building.

The decision is arithmetic plus a short list of qualitative requirements. This chapter gives you
both — and the on-device half becomes your unfair advantage in Chapter 30.

---

## 28.1 · When self-hosting genuinely wins

Five reasons. Note that "it's cheaper" is only one of them, and it's the one that's usually
wrong.

**1 · Data cannot leave.** Regulatory, contractual, or classified. Not "we'd prefer not to" —
actually cannot. This is the strongest and most common legitimate reason.

**2 · Offline or on-device.** No connectivity, or the latency of a round trip is unacceptable.
**This is Chapter 30's territory.**

**3 · Volume, above the break-even.** Section 28.5 gives you the calculation. It exists, and it's
higher than people guess.

**4 · Latency floor.** A local small model can respond in tens of milliseconds. No network call
can.

**5 · Control.** No deprecations, no rate limits, no silent model changes, no vendor. You decide
when anything changes.

### And the honest costs

- **Quality.** Open models have closed much of the gap and have not closed all of it, especially
  on hard reasoning and long-context work. Measure on *your* task.
- **Operations.** You now run GPU inference. Capacity, scaling, monitoring, upgrades, on-call.
  **This is the cost people underestimate by the largest margin.**
- **Capability lag.** New techniques land on hosted APIs first.
- **Engineering time.** The hours spent on serving are hours not spent on retrieval quality.

---

## 28.2 · The VRAM arithmetic

This determines what you can run, and it's simple enough to do in your head.

```
   memory for weights  ≈  parameters × bytes per parameter

   Precision      Bytes/param    7B model    70B model
   ─────────      ───────────    ────────    ─────────
   fp16 / bf16        2           14 GB       140 GB
   int8               1            7 GB        70 GB
   4-bit            0.5           3.5 GB       35 GB
```

Then add the **KV cache**, which is the part people forget:

```
   KV cache  ≈  2 × layers × heads × head_dim × context_length × batch × bytes
```

The number that matters: **KV cache grows linearly with context length and batch size**, and at
long contexts it can exceed the weights themselves. A 7B model that fits comfortably at 2K
context may not fit at 128K.

**Practical rule:** budget weights + 20–40% for KV cache and overhead, then check at your actual
maximum context and batch size, not at your minimum.

```
   Consumer GPU, 24 GB VRAM:
     7B  at fp16  (14 GB)  ✓ comfortable
    13B  at fp16  (26 GB)  ✗ won't fit
    13B  at 4-bit (6.5 GB) ✓ comfortable
    70B  at 4-bit (35 GB)  ✗ needs two, or offloading
```

---

## 28.3 · Quantization

Reducing numeric precision to trade quality for memory and speed. The same idea as section 12.2,
applied to model weights.

| Precision | Memory | Quality | Use for |
|---|---|---|---|
| fp16 / bf16 | 1× | Reference | Serving where memory allows |
| int8 | 0.5× | Very close | A good default |
| **4-bit** | **0.25×** | **Small but real loss** | **The usual sweet spot** |
| 3-bit and below | 0.19×− | Noticeable degradation | Only when forced |

**4-bit is where most people land.** It typically makes a model one size class bigger runnable on
the same hardware, and — this is the important comparison — **a 4-bit larger model usually beats
an fp16 smaller one.**

> **Quantization degrades unevenly.** Loss often shows up first on reasoning, long context, and
> code — the things you're most likely to care about — while short factual answers look fine. So
> a casual test will tell you everything is fine when it isn't.
>
> **Always evaluate a quantized model on your own eval suite**, not by trying a few prompts.
> Chapter 22 exists for exactly this.

---

## 28.4 · The runtimes

Three categories, for three jobs.

### Local single-user — llama.cpp and friends

C++ inference, CPU or GPU, runs well on laptops and even phones. `Ollama` wraps it in a friendly
CLI and an HTTP API that's close enough to standard shapes to swap in easily.

```bash
ollama pull <model>
ollama run <model> "Explain retrieval-augmented generation."
```

**Use for:** development, privacy-sensitive local work, offline tools, and — crucially —
**on-device deployment, which is Chapter 30.**

### Production serving — vLLM and similar

Built for throughput. The techniques that matter:

- **Continuous batching** — new requests join an in-flight batch instead of waiting for it to
  finish. This is the single biggest throughput win.
- **PagedAttention** — manages KV cache like virtual memory, so memory isn't wasted on padding.
- **Tensor parallelism** — splits a model across GPUs.

Exposes an OpenAI-compatible API, so your client code often needs no changes.

**Use for:** serving many concurrent users from your own infrastructure.

### Managed open-model hosting

Someone else runs an open model for you, billed per token. **The underrated middle option** — you
get open weights and no operations, and it's usually where you should *start* if your reason for
open models is licensing or control rather than data residency.

---

## 28.5 · The break-even calculation

Do this before deciding. It's the part people skip.

```
   Hosted:       cost per 1M tokens, input and output, from the price table
   Self-hosted:  GPU cost per hour ÷ tokens produced per hour
```

The method, with the *structure* rather than prices that will age:

```
   1. Measure your actual throughput on your actual hardware, at your
      actual batch size and context length.  ← nobody does this and it
      changes the answer by 5–10×

   2. Compute:  cost/hour ÷ (tokens/second × 3600)  =  cost per token

   3. Compare against the hosted rate for the model you'd otherwise use.

   4. Now add the parts people omit:
        · utilisation — a GPU idle at 3am still costs you
        · redundancy  — one GPU is not a production deployment
        · engineering — your time, at your rate
        · on-call     — the cost of being woken up
```

**Step 4 is where most self-hosting cases fall apart.** A GPU running at 20% utilisation costs
five times its nominal per-token rate, and "one instance" isn't a deployment.

> **The honest heuristic:** for most application teams, self-hosting a *generation* model breaks
> even somewhere in the tens of millions of tokens per month, *sustained and well-utilised*.
> Below that, hosted wins on total cost including your time.
>
> **Embedding models are a different story** — they're small, fast, and cheap to run, and
> self-hosting them often makes sense at far lower volumes. If you self-host one thing, make it
> embeddings.

---

## 28.6 · Measuring the quality gap

Do not accept a benchmark. Run your own suite.

```
                          hosted (large)   open 4-bit (mid)   Δ
  task accuracy               0.89              0.81        −0.08
  format compliance           0.99              0.94        −0.05
  tool selection              0.93              0.76        −0.17   ← the gap
  long-context recall         0.88              0.62        −0.26   ← and here
  p95 latency                 890ms             240ms       −73%
  cost per 1M tok            $25.00            $2.10        −92%
```

That table is the decision, and note *where* the gaps are. Open models often hold up well on
straightforward generation and fall off on **tool use and long context** — which are precisely
what Parts III and IV depend on.

**Hybrid architectures follow directly:** a local model for classification, routing, extraction
and embedding; a hosted model for the hard reasoning. Section 25.3's routing, with a bigger
spread.

---

## 28.7 · Build it

```
src/genai_toolkit/local/
├── runtime.py       LocalModel implementing your LLMClient Protocol
├── ollama.py
├── vllm.py
└── benchmark.py     throughput, latency, VRAM
```

Requirements:

1. **A local model behind your existing `LLMClient` Protocol**, swappable by config with no
   changes to your pipeline. *(This is Chapter 6's abstraction paying off.)*
2. **Run your full eval suite** against local and hosted. Produce the 28.6 table.
3. **Quantization comparison** — same model at fp16, int8 and 4-bit, evaluated on your suite, not
   on vibes.
4. **A throughput benchmark**: tokens/second at batch sizes 1, 4, 16, 64, and at short and long
   context.
5. **Your own break-even calculation**, with the step-4 factors included.
6. **A hybrid route** — something cheap running locally, something hard running hosted, with
   per-route eval scores.
7. `make check` green.

### The experiments

**1 · Find the quantization cliff.** Run your eval suite at fp16, int8, 4-bit and 3-bit. **Find
where it falls off, and note which metrics fall first.** They won't be the ones you'd guess.

**2 · Throughput versus batch size.** Plot it. Understand why continuous batching matters — the
curve is dramatic.

**3 · Measure the KV cache.** Watch VRAM at 1K, 8K and 32K context. Confirm the arithmetic in
28.2.

**4 · Your real break-even.** With measured throughput, at 60% utilisation, with redundancy, with
your hourly rate. **Then decide honestly.**

**5 · The hybrid split.** Route classification and extraction locally, reasoning to hosted.
Measure quality, cost and latency. Report whether you'd ship it.

**6 · Laptop inference.** Run a small model on your own machine. Measure tokens/second and
memory. **This is Chapter 30's baseline** — and your phone will be considerably slower.

---

## 28.8 · Checkpoint

> **Move on to Chapter 29 when all of these are true.**

**Explain, out loud:**

1. The five legitimate reasons to self-host, and which is strongest.
2. The VRAM arithmetic, including why the KV cache matters at long context.
3. Why a 4-bit larger model usually beats an fp16 smaller one.
4. Why quantization damage shows up unevenly, and what that means for how you test it.
5. What continuous batching does and why it's the biggest throughput lever.
6. The break-even calculation, including the four factors people omit.
7. Why embeddings are the easiest thing to self-host.

**Verify:**

8. A local model runs behind your existing Protocol with no pipeline changes.
9. You have the hosted-versus-local eval table for your own task.
10. You have found your quantization cliff.
11. You have computed your own break-even with realistic utilisation.
12. A hybrid route runs, with per-route eval scores.

---

## 28.9 · Going deeper (optional)

**Read the vLLM paper** on PagedAttention. The analogy to virtual memory is genuinely elegant and
it explains most of modern serving throughput.

**Read about speculative decoding.** A small model drafts tokens, a large one verifies them in
parallel. Real speedups, and a clever idea.

**If you're heading toward Chapter 30:** look into the mobile inference runtimes and the small
model families designed for on-device use. Chapter 30 builds on exactly this.

**If you want the licensing angle:** read the actual licences of the open models you're
considering. "Open weights" covers a wide range of terms, and some have usage restrictions that
matter commercially.

---

<div align="center">

**[← Chapter 27](../ch27-fine-tuning/)** · **[The Book](../../readme.md)** · **[Chapter 29 → Multimodal](../ch29-multimodal/)**

*Chapter 28 of 31 · Week 28*

</div>
