# Chapter 27 · Fine-Tuning

### How it works, and the much more valuable skill of knowing when not to

> **Week 27 · ~22 hours · Runs alongside your job search**
>
> This is chapter 27, not chapter 7, and that ordering is the chapter's main argument. Most
> problems people try to solve with fine-tuning are better solved by something you learned in
> Parts II–V.

---

## 27.0 · Why this chapter exists

Fine-tuning has enormous mindshare relative to how often it's the right answer. It sounds like
the serious option — you're not just *prompting* a model, you're *training* one. It's also the
thing hiring managers ask about, so you need to be able to discuss it credibly.

Here is the misconception at the centre of almost every bad fine-tuning decision:

> **Fine-tuning teaches a model *form*, not *facts*.**
>
> It changes how a model behaves — tone, format, style, task structure, the shape of a good
> answer in your domain. It is a poor and expensive way to give a model knowledge, and it makes
> that knowledge impossible to update or cite.

Most people who want to fine-tune actually want the model to *know something*, and the answer to
that is Part III.

So this chapter spends its first section talking you out of it, which is the genuinely valuable
content. Then it teaches you to do it properly, because sometimes it is right — and because
being able to explain *why you didn't* is a stronger interview answer than having done it for no
reason.

---

## 27.1 · The decision tree

Work down this. Stop at the first match.

```
What do you actually want?

├─ "The model should know our internal information"
│     → RAG. Part III.
│     Fine-tuning bakes facts into weights: unciteable, unupdatable,
│     and it still hallucinates around the edges.
│
├─ "The model should follow a specific output format"
│     → Structured output. Chapter 8.
│     Schema-constrained generation makes the format guaranteed.
│     Fine-tuning makes it likely.
│
├─ "The model should use our tools correctly"
│     → Better tool descriptions. Chapter 16.
│     The description is the prompt; fix it before training anything.
│
├─ "The model should behave differently"
│     → Prompt engineering, measured. Chapter 7.
│     Try five measured prompt versions first. Most 'we need to
│     fine-tune' conclusions die here.
│
├─ "It's too expensive / too slow"
│     → Lower effort, route, cache. Chapters 9 and 25.
│     Distilling to a smaller fine-tuned model is a real technique —
│     but it is the LAST cost lever, not the first.
│
├─ "Retrieval doesn't find the right things in our domain"
│     → Fine-tune the EMBEDDING model or the reranker, not the
│       generator. Section 27.7. Often the highest-ROI training you
│       can do, and almost nobody considers it.
│
└─ "We need consistent behaviour that prompting can't reliably achieve,
    at a volume where the cost is worth it, on a task with a stable
    definition, and we have hundreds of high-quality examples"
      → Now fine-tuning might be right. Read on.
```

### The three conditions

Fine-tuning is plausibly correct when **all three** hold:

**1 · The behaviour is hard to specify but easy to demonstrate.** A house style, a domain-specific
reasoning pattern, a classification boundary that takes three pages to describe and one example
to show.

**2 · Volume justifies it.** Fine-tuning a smaller model to match a larger one's quality on a
narrow task is a real and valuable technique — at millions of requests, the savings dwarf the
training cost. At thousands, they don't.

**3 · The task is stable.** Training encodes a snapshot. If your requirements change monthly,
you're signing up for a retraining treadmill, and a prompt change takes seconds.

### And three conditions that mean don't

- **Your data changes.** Facts go in context, not in weights.
- **You need citations.** A fine-tuned model cannot tell you where it learned something.
- **You haven't measured a prompting baseline.** You cannot know fine-tuning helped without a
  number to beat.

> **The strongest thing you can say in an interview about fine-tuning is that you evaluated it
> and decided against it, with reasons.** That demonstrates judgment. "We fine-tuned it"
> demonstrates that you spent money.

---

## 27.2 · What it actually does

Pretraining (section 5.9) set billions of parameters by predicting the next token across
trillions of tokens. Fine-tuning continues that process on *your* examples, at a much lower
learning rate, so the model nudges toward your data without forgetting everything else.

```
   base model  ──────────────────────▶  your examples  ──────▶  adapted model
   (broad capability)                   (500–50,000)            (same capability,
                                                                 your behaviour)
```

**What changes:** output style and tone, format adherence, task-specific reasoning patterns,
domain vocabulary, classification boundaries.

**What doesn't reliably change:** factual knowledge (unreliably absorbed, impossible to update),
reasoning capability (fine-tuning doesn't make a model smarter), and the tendency to hallucinate
— which if anything can get *worse*, because the model becomes more confident in your domain's
register while remaining just as ignorant of what it doesn't know.

### Catastrophic forgetting

Train hard on a narrow task and general capability degrades. Your customer-service model becomes
excellent at customer service and noticeably worse at everything else — including edge cases in
customer service that weren't in your training data.

**Defences:** low learning rates, few epochs, LoRA rather than full fine-tuning, and mixing in
some general data. But the effect is real, and it's why you evaluate on a *broad* set, not just
your task.

---

## 27.3 · Full, LoRA, QLoRA

```
   FULL FINE-TUNING
   ┌───────────────────────────────────┐
   │ ████████████████████████████████  │  every parameter updated
   └───────────────────────────────────┘
   Best quality · enormous memory · a full model copy per task

   LoRA
   ┌───────────────────────────────────┐
   │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │  base frozen
   │        ▲▲▲                        │  small trainable adapters
   └───────────────────────────────────┘
   ~0.1–1% of parameters · near-full quality · adapters are megabytes

   QLoRA
   ┌───────────────────────────────────┐
   │ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  │  base quantized to 4-bit, frozen
   │        ▲▲▲                        │  LoRA adapters on top
   └───────────────────────────────────┘
   Fits on one consumer GPU · slightly lower quality · slower training
```

### LoRA, intuitively

The insight: the *update* a fine-tune needs to make is low-rank — it can be approximated by two
small matrices multiplied together, rather than one enormous one.

```
   A weight matrix might be 4096 × 4096  =  16.8M parameters
   Its LoRA update:  4096 × 8  +  8 × 4096  =  65K parameters

   0.4% of the size. Most of the benefit.
```

The base model is frozen; only the adapters train. Three consequences that matter practically:

- **Small artefacts.** Adapters are megabytes, not gigabytes. You can store dozens.
- **Swappable.** One base model, many adapters, chosen per request.
- **Cheap to train.** Far less memory, far less time.

The rank `r` is your main dial: 8 or 16 for style and format, 32–64 for more substantial
behavioural change. Higher isn't automatically better — it's more capacity to overfit with.

### QLoRA

Quantize the frozen base to 4-bit, then train LoRA on top. Memory drops enough that a model you
couldn't load at all now fine-tunes on a single consumer GPU.

**The practical recommendation: start with LoRA, or QLoRA if memory forces it.** Full fine-tuning
is rarely worth its cost for application work.

---

## 27.4 · The data is the project

> **Fine-tuning is 90% data work and 10% training.** The training is a command. The data is
> weeks.

### Quality beats quantity, decisively

```
   500 excellent, consistent examples    ≫    50,000 mediocre inconsistent ones
```

The model learns your data's patterns — **including its mistakes and inconsistencies.** Ten
percent of your examples using a different format teaches the model to use that format ten
percent of the time, forever.

### Rough quantities

| Goal | Examples |
|---|---:|
| Output format and style | 100–500 |
| Domain tone | 500–2,000 |
| A specific task | 1,000–10,000 |
| Distilling a larger model | 10,000–100,000 |

### The checklist

- [ ] **Consistent.** Same format, same conventions, same level of detail throughout.
- [ ] **Representative.** Matches your real input distribution, including the awkward inputs.
- [ ] **Correct.** Every example is what you actually want. **Read them.** A bad example is
      worse than a missing one.
- [ ] **Includes edge cases** — and includes what to do when the answer is *"I don't know."*
      Otherwise you train a model that always answers.
- [ ] **Deduplicated.** Near-duplicates skew the distribution.
- [ ] **Split.** Train / validation / test, held out properly.
- [ ] **No leakage.** Test examples must not appear in training in any form.

### Where the data comes from

**Real production data** is best — real inputs with reviewed correct outputs. Your traces
(Chapter 23) are the source.

**Distillation** — a stronger model produces outputs, humans review and correct them, the
corrected set trains a smaller one. Cost-effective, and the *review* step is what makes it work.
Skip it and you're training on the larger model's mistakes.

**Human-written** — highest quality, slowest. Right for small, high-value sets.

> **Whatever the source, read a random 50 before you train.** You will find inconsistencies.
> Fix them. This is the same instruction as "read your chunks" in section 11.10, for the same
> reason and with the same neglect rate.

---

## 27.5 · Training, practically

```python
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    r=16,                       # rank — capacity of the adapter
    lora_alpha=32,              # scaling; a common convention is 2 × r
    target_modules=["q_proj", "v_proj"],   # which layers get adapters
    lora_dropout=0.05,
    task_type="CAUSAL_LM",
)

model = get_peft_model(base_model, lora_config)
model.print_trainable_parameters()
# trainable: 4,194,304 || all: 6,742,609,920 || trainable%: 0.0622
```

The hyperparameters that actually matter:

| Parameter | Typical | Effect |
|---|---|---|
| **Learning rate** | 1e-4 to 2e-4 (LoRA) | The main dial. Too high and it forgets; too low and nothing happens |
| **Epochs** | 1–3 | **More than 3 usually overfits.** Watch validation loss |
| **`r`** | 8–64 | Adapter capacity |
| **Batch size** | As large as memory allows | Stability |
| **Warmup** | ~3% of steps | Avoids a destructive first update |

### Reading the loss curves

```
   loss
    │╲
    │ ╲___ training
    │     ╲______
    │  ___╱              ← validation turning UP: overfitting. Stop here.
    │ ╱
    └──────────────▶ steps
```

**Validation loss rising while training loss falls is the signal to stop.** Checkpoint every
epoch and keep the best validation checkpoint, not the last one.

If both losses plateau high, your learning rate is too low or your data doesn't contain the
pattern you think it does. If loss goes to near-zero immediately, you probably have leakage
between train and validation.

---

## 27.6 · Evaluating a fine-tune

**This is Chapter 22 again, with two additions.** And it's non-negotiable: without it you cannot
know whether you improved anything.

Evaluate on three sets:

**1 · Your task's test set.** Did it get better at what you trained it for? Compare against your
prompted baseline on the *same* cases.

**2 · A general capability set.** Did it get worse at everything else? This is your
catastrophic-forgetting check, and it's the one people skip.

**3 · Your production eval suite.** End to end, in your actual system.

```
                        prompted baseline    fine-tuned    Δ
  task accuracy               0.78             0.89      +0.11
  format compliance           0.83             0.99      +0.16
  general capability          0.91             0.84      −0.07   ← the cost
  cost per request          $0.0068          $0.0011      −84%
  p95 latency                 890ms            310ms      −65%
```

That table is the decision. **A fine-tune that improves your task and degrades general capability
may still be right** — if your system only ever does that task. It's wrong if the model also
handles anything else.

And note the last two rows: the strongest case for fine-tuning in application work is usually
**cost and latency at volume**, not raw quality.

---

## 27.7 · The one people miss: fine-tuning retrieval

**For most application engineers, this has better ROI than fine-tuning a generator**, and almost
nobody considers it.

Section 10.5's failure: a general embedding model doesn't know your domain's vocabulary.
"Blorptastic Widget" lands somewhere arbitrary; two terms that are synonyms in your industry are
far apart in the vector space.

**Fine-tuning an embedding model on your own query/document pairs fixes exactly that**, and it's
cheap:

- Embedding models are small — training is fast and runs on modest hardware.
- **The training data is free.** Your gold set from Chapter 14 *is* query/relevant-document pairs.
  You already built it.
- It improves the stage that most limits your system's quality.
- The improvement is directly measurable with the metrics you already have.

The same applies to **reranker** fine-tuning, often with an even better return, because the
reranker is the stage with the most influence on what actually reaches the model (section 14.6).

```
   Typical returns on a specialised domain:

   fine-tune the generator   →  quality +0.03, cost of a training project
   fine-tune the embeddings  →  recall@10 +0.08, an afternoon
```

Those numbers are illustrative, not universal. **Measure both on your own corpus** — but try the
embedding one first, because it's an afternoon and it uses data you already have.

---

## 27.8 · The honest costs

**Training:** a small LoRA run on a rented GPU is tens of dollars. Full fine-tuning of a large
model is thousands. Hosted fine-tuning services sit in between, priced per token.

**Serving:** the real cost, and the one people underestimate. A hosted fine-tune usually costs
more per token than the base model. A self-hosted one means you now operate GPU inference —
capacity planning, scaling, on-call. That's a permanent operational commitment, not a one-off.

**Maintenance:** base models improve. In six months there's a better one, and your fine-tune sits
on an older foundation. Redoing it means re-running data prep, training and evaluation. **Budget
for retraining, or accept that your fine-tune has a shelf life.**

**Opportunity:** the two weeks spent fine-tuning could have gone into retrieval quality, evals or
prompt iteration — which, for most application systems, return more.

---

## 27.9 · Build it

Two exercises. **The second is the one that matters for your career.**

### 1 · One real fine-tune, end to end

Do it once so you understand it from the inside. Keep it small.

```
finetune/
├── data/
│   ├── prepare.py       collect, clean, dedupe, split
│   ├── inspect.py       ← read 50 examples. Required.
│   └── validate.py      format and leakage checks
├── train.py             LoRA/QLoRA config and run
├── evaluate.py          all three eval sets
└── FINDINGS.md
```

Requirements:

1. A **narrow, well-defined task** with a clear prompted baseline.
2. **500–2,000 examples**, cleaned, deduplicated, split, and **read by you**.
3. A leakage check between splits.
4. LoRA or QLoRA, with loss curves plotted.
5. **Evaluation on all three sets**, with the comparison table from 27.6.
6. `FINDINGS.md` with a **ship / don't ship recommendation** and its reasoning.

### 2 · Fine-tune your retrieval — the higher-ROI one

Take your Chapter 14 gold set. Fine-tune an embedding model on those pairs. Measure recall@10
before and after on the held-out test split.

**This is likely to produce a bigger improvement to your actual system than the generator
fine-tune, in a fraction of the time, using data you already have.** If you only do one, do this
one.

### 3 · The decision memo

For a real problem in one of your projects, write a one-page memo: should we fine-tune?

- What behaviour we want, and why prompting falls short — **with the measured baseline**
- Data required, and whether we have it
- Training and serving cost estimates
- What we'd measure to know it worked
- **The recommendation, which may well be no**

**That memo is a portfolio artefact**, and a "no, and here's the analysis" is a stronger one than
a yes.

---

## 27.10 · Exercises

**1 · Kill it with prompting.** Take a task you think needs fine-tuning. Write five measured
prompt versions (Chapter 7). **How close do you get?** Most of the time, close enough.

**2 · Data quality experiment.** Fine-tune on 500 carefully cleaned examples, then on 2,000
including 20% inconsistent ones. **Measure both.** The smaller clean set usually wins, and seeing
it is worth more than being told.

**3 · Find the overfitting point.** Train for 1, 2, 3 and 5 epochs. Plot validation loss and task
accuracy. Find where they diverge.

**4 · Catastrophic forgetting, measured.** Evaluate general capability before and after a
deliberately aggressive fine-tune. Quantify the damage.

**5 · Rank sweep.** Train at `r` = 4, 8, 16, 32, 64. Plot quality against adapter size and
training time. Find your knee.

**6 · Adapter swapping.** Train two LoRA adapters for different tasks on one base model. Swap
between them at inference. This is the deployment pattern that makes LoRA attractive.

**7 · The embedding fine-tune.** Section 27.7. Measure recall before and after. **Compare the
improvement per hour spent against the generator fine-tune.**

**8 · Total cost of ownership.** For a real fine-tune, compute: training, serving at your volume,
and retraining twice a year. Compare against the prompted baseline's cost. **At what volume does
it break even?**

---

## 27.11 · Checkpoint

> **Move on to Chapter 28 when all of these are true.**

**Explain, out loud:**

1. Why fine-tuning teaches form and not facts, and what that rules out.
2. The decision tree, and the six branches that lead somewhere other than fine-tuning.
3. The three conditions that must all hold.
4. How LoRA works, intuitively, and why the adapters are small.
5. What catastrophic forgetting is and how you'd detect it.
6. Why 500 clean examples beat 50,000 messy ones.
7. Why fine-tuning embeddings is often better value than fine-tuning the generator.
8. The real costs — serving and maintenance, not training.

**Verify:**

9. You have completed one small fine-tune end to end, with loss curves.
10. You evaluated on all three sets and have the comparison table.
11. **You have fine-tuned an embedding model on your Chapter 14 gold set and measured the
    recall change.**
12. You have written a decision memo, and you can defend its recommendation either way.

Number 11 is the one that will actually improve a system you own.

---

## 27.12 · Going deeper (optional)

**[Appendix C · How Fine-Tuning Actually Works](../../appendices/C-finetuning-maths.md)** — gradients, backpropagation
and the low-rank decomposition behind LoRA, with every symbol explained.

**Read the LoRA paper.** Short, clearly written, and the core idea is genuinely elegant. You'll
understand `r` properly afterwards.

**Read the QLoRA paper** if memory constraints are real for you. The quantization techniques are
interesting well beyond fine-tuning.

**If you want the practical path:** the `peft` and `trl` library documentation, and the
`sentence-transformers` training guide for the embedding case in 27.7. The last one is the
shortest route to a result that matters.

**If you want the honest counterweight:** search for write-ups from teams who fine-tuned and
concluded it wasn't worth it. They're less common than success stories and considerably more
instructive.

---

<div align="center">

**[← Project E](../../part-5-production/project-e-to-production/)** · **[The Book](../../readme.md)** · **[Chapter 28 → Local & Open Models](../ch28-local-models/)**

*Chapter 27 of 31 · Week 27 · Part VI begins*

</div>
