# Chapter 5 · What an LLM Actually Is

### Tokens, embeddings, attention, and why confident nonsense is a feature of the mechanism

> **Week 5 · ~22 hours · Concepts, with small experiments**
>
> The most important conceptual chapter in the book. Everything in Parts III, IV and V is
> an engineering response to something explained here. When retrieval fails in Chapter 15
> or an agent loops forever in Chapter 17, the explanation will be in this chapter.

---

## 5.0 · Why this chapter exists

You can build things with an LLM while treating it as a magic box. Plenty of people do.
They get a working demo in an afternoon, and then they hit a wall that they cannot get past,
because every problem beyond the demo requires knowing *why* the box behaves as it does.

Some real questions you will face in the next six months:

- Why does the model insist "strawberry" has two R's?
- Why does the same prompt work on Monday and fail on Thursday?
- Why does stuffing more context into the prompt sometimes make answers *worse*?
- Why does it invent a plausible-looking function that doesn't exist in the library?
- Why is my first token slow but the rest fast?
- Why does asking it to "think step by step" genuinely improve the answer?

Every one of those has a precise mechanical answer, and every answer is in this chapter.
You don't need mathematics to understand them. You need an accurate mental model of what
happens between your prompt going in and text coming out.

That's what we're building. No equations in the main text — they're in
[Appendix A](../../appendices/) if you want them, and you genuinely don't need them for the
job.

---

## 5.1 · The one-sentence answer

Here is what a large language model does:

> **Given a sequence of text, it predicts what comes next. Then it appends that and
> predicts again. That's it.**

That's the whole thing. Not a simplification you'll later replace with something more
sophisticated — the actual mechanism, all the way down.

```
"The capital of France is"       →  " Paris"
"The capital of France is Paris" →  "."
"The capital of France is Paris."→  [stop]
```

This is called **autoregressive generation**: each prediction is fed back in as input for
the next. The model runs once per token. A 500-token answer means 500 forward passes.

### The obvious objection

"That can't be right. It writes working code. It explains my architecture. It catches bugs I
missed. Autocomplete doesn't do that."

The objection is reasonable and the resolution is genuinely interesting: **predicting the
next token well enough, at sufficient scale, requires building internal machinery that
looks a great deal like understanding.**

Think about what it takes to reliably complete this:

```
"def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci("
```

To get `n-2` right, something inside must have represented: this is Python, this is a
recursive function, the recursive case needs two calls, the first was `n-1`, the pattern
requires the second to be `n-2`. You cannot get that from surface statistics. You get it
from having learned structure.

Scale this across trillions of tokens of text — code, science, argument, translation,
fiction — and the machinery required to predict well becomes something that can *do* things.
That's the surprise of the last few years, and nobody fully predicted it.

> **Hold both ideas at once.** The mechanism is next-token prediction. The capability is
> far richer than that sounds. Drop the first and you'll expect abilities the model doesn't
> have. Drop the second and you'll underuse it badly.

---

## 5.2 · Tokens

The model does not see letters, and it does not see words. It sees **tokens**.

### What a token is

Text is split into pieces from a fixed vocabulary — typically somewhere around 100,000
entries, each mapped to an integer ID. Common words are single tokens; rare words are
assembled from fragments.

```
"The cat sat"        →  ["The", " cat", " sat"]                  3 tokens
"unbelievable"       →  ["un", "bel", "iev", "able"]             4 tokens
"antidisestablish"   →  ["anti", "dis", "establish"]             3 tokens
"🎉"                 →  possibly several tokens
"def fibonacci(n):"  →  ["def", " fib", "on", "acci", "(", "n", "):"]
```

Notice the leading spaces: `" cat"` (with space) and `"cat"` (without) are *different
tokens* with different IDs. This detail matters more than it seems.

### Why text is split this way

The vocabulary is built by an algorithm — usually **Byte-Pair Encoding** — that starts from
individual characters and repeatedly merges the most frequent adjacent pair into a new
token. Run it long enough and you get a vocabulary where common words are whole and rare
words decompose into reusable fragments.

It's a compromise between two bad extremes:

| Approach | Vocabulary | Problem |
|---|---|---|
| One token per character | ~100 | Sequences become enormous; the model wastes capacity learning spelling |
| One token per word | Millions | Can't handle typos, new words, or most languages |
| **Subword (BPE)** | ~100K | ✅ Fixed size, handles anything, most common words stay whole |

### The practical consequences

This is not trivia. Five things follow directly, and you'll meet all of them.

**1 · You pay per token, not per word.** English averages roughly **0.75 words per token** —
so ~1.33 tokens per word. A 1,000-word document is around 1,300 tokens. Every cost
calculation in Chapter 9 starts here.

**2 · Some languages cost multiples more.** Tokenizers are trained on corpora dominated by
English. The same sentence in Hindi, Thai, or Japanese can consume two to four times the
tokens, because the model has fewer whole-word tokens for those scripts and falls back to
fragments. This is a real fairness and cost issue, and it will surprise you the first time
you serve non-English users.

**3 · The model cannot reliably see letters.** This is the strawberry problem:

```
"strawberry" → ["str", "aw", "berry"]
```

Ask how many R's it contains, and the model is looking at three opaque symbols, not ten
letters. It has *learned* about spelling indirectly, from text discussing spelling, but it
is not counting characters — it's recalling patterns. Sometimes that works. Sometimes it
produces a confidently wrong number.

> **The general rule:** any task requiring character-level manipulation — counting letters,
> reversing strings, precise substring surgery — is working against the representation. Do
> it in code. This is not a model weakness to be prompted around; it's a consequence of
> what the model can see.

**4 · Arithmetic is harder than it looks.** `1234567` may tokenize as `123` + `45` + `67`.
The model isn't manipulating place value; it's pattern-matching over fragments. It's
surprisingly good at this, and it is not a calculator. Give it a calculator tool instead —
Chapter 16.

**5 · Token boundaries affect behaviour.** A prompt ending in a trailing space can tokenize
differently from one without, and occasionally produces different output. It's rare, but
when you're chasing a weird inconsistency, check your whitespace.

### Counting tokens correctly

You'll need exact counts for cost and context budgeting. **Use the provider's endpoint, not
a third-party tokenizer library** — tokenizers are model-specific and a library that matches
one model will silently miscount for another:

```python
count = client.messages.count_tokens(
    model="claude-opus-5",
    system=system_prompt,
    messages=messages,
)
print(count.input_tokens)
```

A rough mental estimate for sanity checks: **1 token ≈ 4 characters ≈ 0.75 English words.**
Use it for napkin maths, never for billing.

---

## 5.3 · From tokens to vectors

A token ID is just an integer — `" cat"` might be `2543`. Integers carry no meaning: `2543`
isn't "close to" `2544` in any useful sense.

So the first thing the model does is look each token up in a giant table, converting it into
a **vector**: a list of numbers, typically a few thousand of them.

```
" cat"  →  [0.21, -0.88, 0.04, 1.32, ..., -0.11]     (e.g. 4096 numbers)
```

These vectors are *learned during training*, and this is where the first bit of magic
happens: **tokens with similar meanings end up with similar vectors.**

```
    " dog"  ────┐
    " cat"  ────┼──  clustered together (animals, pets)
    " horse"────┘

    " Paris" ───┐
    " London"───┼──  clustered together (capital cities)
    " Tokyo" ───┘
```

Nobody programmed those groupings. They emerged because words used in similar contexts
ended up needing similar representations to predict well.

The famous demonstration of the structure:

```
    vector("king") − vector("man") + vector("woman")  ≈  vector("queen")
```

Direction in this space carries meaning. One direction is roughly "gender," another roughly
"plural," another "past tense." The space has thousands of dimensions and most of them
aren't human-interpretable, but the geometry is real.

> **This idea is the entire foundation of Part III.** Chapter 10 takes it much further:
> if meaning is geometry, then *finding relevant documents* becomes *finding nearby points*,
> and that's what makes retrieval possible. Remember this section — you'll come back to it.

One critical limitation: at this stage, `" bank"` has exactly one vector, whether you meant
a river bank or a financial one. The lookup table is context-free. Fixing that is the next
section's job, and it's the reason transformers exist.

---

## 5.4 · Attention

This is the mechanism that made modern language models possible, and it's worth
understanding properly. The name of the paper that introduced it — *"Attention Is All You
Need"* — is not an exaggeration; it's the architecture's thesis.

### The problem it solves

Consider:

> "The **trophy** doesn't fit in the **suitcase** because **it** is too **big**."

What does "it" refer to? The trophy. Now change one word:

> "The **trophy** doesn't fit in the **suitcase** because **it** is too **small**."

Now "it" is the suitcase. The word "it" is identical in both sentences; its meaning is
determined entirely by a relationship to other words, several positions away.

Any system that processes words in isolation, or strictly left-to-right with a fixed-size
memory, struggles badly here. Attention solves it directly.

### What attention does

At every layer, **every token looks at every other token and decides how much each one
matters to it.** Then it updates its own representation by mixing in information from the
tokens it decided were relevant.

For the token `"it"` in that first sentence:

```
        "The"    →  0.01
        "trophy" →  0.62     ← most of the attention goes here
        "doesn't"→  0.02
        "fit"    →  0.08
        "in"     →  0.01
        "the"    →  0.01
        "suitcase"→ 0.15
        "because"→  0.02
        "it"     →  0.05
        "is"     →  0.01
        "too"    →  0.02
        "big"    →  0.00
```

Those weights sum to 1. The representation of `"it"` becomes a blend, dominated by
`"trophy"`. After this operation, `"it"` *is* trophy-ish in the model's internal
representation. The ambiguity is resolved, in place, by the mechanism.

Flip `"big"` to `"small"` and the weights shift toward `"suitcase"`. Nobody wrote a rule for
this. It was learned, because getting it right helps predict the next token.

### The library analogy

The actual implementation gives each token three derived vectors — **query**, **key**, and
**value** — and it works exactly like a soft library search:

- The **query** is what this token is looking for. *"I'm a pronoun. I need a noun I can
  refer to."*
- The **key** is what each token advertises about itself. *"I'm a concrete noun,
  singular, recently mentioned."*
- The **value** is what a token actually contributes when attended to.

Every query is compared against every key. Strong matches get high weights. The token then
receives a weighted blend of the values.

The difference from a real library search is that it's *soft*: you don't get one book, you
get a weighted mixture of all of them. That softness is what makes it learnable — and it's
why the whole thing is differentiable, which is what lets training work at all.

### Multi-head attention

One set of query/key/value comparisons captures one kind of relationship. Real language has
many at once: grammatical subject, coreference, topic, tone, code scope.

So models run many attention operations in parallel — **heads** — each free to specialise.
Interpretability researchers have found heads that appear to track syntactic dependencies,
heads that track quotation, heads that copy from earlier in the text. Their outputs are
combined, and the layer moves on.

### Why this was revolutionary

The predecessors (RNNs, LSTMs) processed text strictly one token at a time, carrying a
fixed-size memory forward. Two fatal problems: long-range dependencies decayed, and — because
step *n* required step *n−1* — **training could not be parallelised**.

Attention looks at all positions simultaneously. Distance costs nothing: token 1 and token
5,000 are one operation apart. And every position can be computed in parallel during
training, which is what made it possible to train on trillions of tokens using thousands of
GPUs.

**Transformers won because they were parallelisable.** The architecture that trains fastest
wins, because it gets to eat more data.

### The cost, and a consequence you'll feel

Every token attending to every other token is an **n² operation**. Double your context, and
attention cost roughly quadruples.

This is why context windows were small for years, why long contexts cost more and run
slower, and why an enormous amount of engineering has gone into making attention cheaper.
It's also, indirectly, why Part III exists: **retrieval is what you do instead of putting
everything in the context window.** You could paste your entire company wiki into a 1M-token
prompt. Retrieval finds the 2,000 tokens that matter — faster, cheaper, and often *more
accurate*, for reasons we'll get to in section 5.11.

---

## 5.5 · The stack

Zooming out, here is the whole forward pass:

```
   your prompt
        │
        ▼
   ┌─────────────┐
   │ TOKENIZER   │   text → token IDs
   └─────────────┘
        │  [791, 8415, 7731]
        ▼
   ┌─────────────┐
   │ EMBEDDINGS  │   IDs → vectors (+ position information)
   └─────────────┘
        │
        ▼
   ┌─────────────┐  ┐
   │  ATTENTION  │  │
   │      +      │  │   Layer 1
   │  FEED-FWD   │  │
   └─────────────┘  ┘
        │
   ┌─────────────┐
   │   Layer 2   │
   └─────────────┘
        │
       ...          ← dozens of layers
        │
   ┌─────────────┐
   │   Layer N   │
   └─────────────┘
        │
        ▼
   ┌─────────────┐
   │  UNEMBED    │   final vector → score for EVERY token in the vocabulary
   └─────────────┘
        │
        ▼
   ┌─────────────┐
   │  SAMPLING   │   scores → probabilities → pick one
   └─────────────┘
        │
        ▼
    next token
```

Each layer does two things: **attention** (gather information from other positions) and a
**feed-forward network** (process what was gathered, at each position independently).

A rough and useful intuition, supported by interpretability research though not a complete
picture:

- **Early layers** work on surface structure — syntax, parts of speech, resolving what
  refers to what.
- **Middle layers** build meaning — entities, relationships, facts, the semantic content.
- **Late layers** work backward toward output — what should come next, in what register,
  in what format.

The feed-forward layers are where most of the model's *parameters* live, and there's good
evidence they act as a kind of learned key-value memory — the place where factual
associations are stored. Attention moves information around; feed-forward layers are where
a lot of "knowing things" lives.

Everything flows through a **residual stream**: each layer *adds* its contribution to a
running representation rather than replacing it. Think of it as a shared whiteboard that
every layer reads from and writes to. This is a small architectural detail with large
consequences — it's what allows very deep networks to train at all.

---

## 5.6 · Probabilities, and picking a token

After the final layer, the model produces a score for **every single token in its
vocabulary** — all ~100,000 of them. These raw scores are called *logits*. A function called
softmax converts them into probabilities that sum to 1.

```
Prompt: "The capital of France is"

    " Paris"      →  0.89
    " the"        →  0.04
    " located"    →  0.02
    " a"          →  0.01
    " Lyon"       →  0.003
    " banana"     →  0.0000001
    ... 100,000 more, each with some probability
```

**Every token has a non-zero probability.** Including " banana". That's worth sitting with,
because it's the root of a lot of behaviour.

Now the model must pick one. How it picks is entirely under your control, and this is the
part most people never learn properly.

---

## 5.7 · Sampling: temperature and top-p

### Temperature

Temperature reshapes the probability distribution before sampling — it makes it sharper or
flatter.

```
temperature = 0.0          temperature = 1.0         temperature = 2.0
(sharpest / greedy)        (unmodified)              (flattened)

" Paris"    ~1.00          " Paris"    0.89          " Paris"    0.41
" the"       0.00          " the"      0.04          " the"      0.15
" located"   0.00          " located"  0.02          " located"  0.11
" Lyon"      0.00          " Lyon"     0.003         " Lyon"     0.06
```

At **0**, always take the most likely token. Nearly deterministic. At **1**, sample from the
distribution as the model produced it. Above **1**, flatten it — unlikely tokens get a real
chance, and output becomes erratic.

> **Temperature is not a creativity dial.** It's a *risk* dial. High temperature doesn't
> make the model more imaginative; it makes it more willing to pick tokens it thinks are
> probably wrong. Sometimes that reads as creative. Often it reads as incoherent, and in a
> factual task it reads as *hallucinating*.

What to use, in practice:

| Task | Temperature | Why |
|---|---|---|
| Extraction, classification, structured output | **0** | You want the most likely answer, repeatably |
| Factual Q&A, RAG answers | **0 – 0.3** | Accuracy over variety |
| Code generation | **0 – 0.3** | There are few correct programs |
| Conversation | **0.5 – 0.8** | Some variation feels natural |
| Brainstorming, fiction | **0.8 – 1.0** | Variety is the point |

**A caution about temperature 0:** it reduces randomness dramatically but does not guarantee
byte-identical output across requests. Floating-point non-determinism on GPUs, batching, and
infrastructure changes all introduce variation. Design for "very consistent," never for
"exactly reproducible." If your tests assume the latter, they will fail mysteriously.

### Top-p (nucleus sampling)

An alternative knob, often used alongside temperature. Top-p keeps only the smallest set of
tokens whose probabilities add up to `p`, then samples within that set.

```
top_p = 0.9  →  keep tokens until cumulative probability reaches 0.9, discard the rest
```

Its virtue is that it *adapts*. When the model is confident ("The capital of France is…"),
the top token alone may exceed 0.9, so only that one survives. When the model is genuinely
uncertain ("My favourite colour is…"), many tokens are needed to reach 0.9, so variety
survives.

Top-p cuts off the long tail of nonsense while preserving legitimate variation. That's a
better shape than temperature alone.

> **Practical advice:** tune one, not both. Most of the time, set temperature and leave
> top-p alone. And note that on the newest models with adaptive thinking, sampling
> parameters like `temperature` and `top_p` are no longer accepted at all — the reasoning
> machinery handles this internally, and you steer with `effort` instead. Check what your
> target model supports rather than assuming.

---

## 5.8 · Why models hallucinate

You now have everything needed to understand this properly, and understanding it
mechanically is what lets you engineer around it.

### The core reason

Look again at what the model computes: **a probability distribution over next tokens.** Every
time. Unconditionally.

Ask a question it learned well, and the high-probability continuation *is* the correct
answer. Ask a question it never learned, and there is still a high-probability continuation —
it's just the most *plausible-sounding* text rather than the true text.

**The model performs the identical operation in both cases.** There is no internal switch
that flips to "I don't know." From the inside, answering correctly and confabulating are the
same computation.

This is why hallucinations are:

- **Fluent** — fluency is exactly what's being optimised
- **Confident** — no uncertainty is being expressed, because none is being computed
- **Plausible** — plausible *is* the objective function
- **Specific** — invented citations have page numbers because real ones do

An invented API method looks exactly like a real one because the model learned the *shape*
of API methods. The shape is right. The fact is absent.

### Why "I don't know" is hard to learn

Human-written text has a strong bias: people mostly write about what they know. Very little
of the training corpus consists of confident statements followed by "actually, I have no
idea." So "confident assertion" is heavily represented and "calibrated uncertainty" is not.

Post-training (section 5.9) works hard to teach models to express uncertainty, and modern
models are substantially better at it than early ones. But it's pushing against the grain of
both the data and the objective.

### The second reason: the ratchet

Autoregressive generation feeds output back as input. A wrong token at position 12 becomes
*context* for position 13.

```
"The DataFrame.pivot_faster() method"  ← invented
"...takes three arguments..."          ← now consistent with the invention
"...as of pandas 2.1..."               ← now elaborating on it
```

The model isn't doubling down out of stubbornness. Each subsequent token is the most likely
continuation *given everything before it*, and everything before it now includes the
mistake. Coherence with the context is what it optimises, and the context is wrong.

This is why a hallucination often arrives as a whole confident paragraph rather than a single
slip.

### What actually helps

Notice that every one of these is an engineering response to the mechanism, and that each
one is a later chapter of this book:

| Intervention | Why it works | Where |
|---|---|---|
| **Put the facts in the prompt (RAG)** | Copying from context is far more reliable than recalling from parameters | Part III |
| **Require citations** | Forces grounding in provided text; makes fabrication visible | Ch 15 |
| **Give it tools** | A calculator computes; a search engine looks up. Neither guesses | Part IV |
| **Lower the temperature** | Fewer low-probability tokens means fewer improvised turns | This chapter |
| **Explicitly permit "I don't know"** | Raises the probability of a refusal path that otherwise loses out | Ch 7 |
| **Ask for reasoning first** | Errors become visible in the reasoning before they're committed to | Ch 7 |
| **Evaluate systematically** | You cannot manage a hallucination rate you don't measure | Ch 22 |

> **The reframe that matters:** hallucination is not a bug awaiting a patch. It is what a
> next-token predictor does when asked something it doesn't know. Your job is not to
> eliminate it — it's to **build systems where the model rarely needs to guess, and where
> guesses are caught when they happen.** Every one of those interventions moves probability
> mass away from improvisation and toward copying.

---

## 5.9 · How models are trained

Three stages. Knowing them explains a lot of behaviour you'll otherwise find mysterious.

### Stage 1 · Pretraining

Show the model an enormous quantity of text — trillions of tokens — and have it predict the
next token, over and over. Wrong predictions produce a small adjustment to the parameters.
Repeat for months, across thousands of GPUs, at a cost in the millions.

This is where essentially **all knowledge and capability** come from. Grammar, facts,
reasoning patterns, programming, translation, style — all of it emerges from this one
objective, applied at absurd scale.

The result is a *base model*: extraordinarily knowledgeable, and almost useless to talk to.
Ask a base model a question and it might continue with more questions, because the training
data contains plenty of question lists. It has no notion of being an assistant.

Two consequences worth remembering:

- **The knowledge cutoff.** The model knows nothing after its data was collected, and
  nothing at all about your private documents. That's what retrieval fixes.
- **The training data's biases are the model's biases.** Skewed data produces skewed
  behaviour. This isn't a moral failing of the architecture; it's an accurate reflection of
  its input.

### Stage 2 · Supervised fine-tuning

Now train on curated examples of good assistant behaviour: a request, and an excellent
response. Tens or hundreds of thousands of them, largely human-written.

This teaches *format and role*, not knowledge. It's where "answer the question" is learned,
where "here's a helpful explanation with an example" is learned, where refusing harmful
requests begins.

Small compared to pretraining, and transformative for usability.

### Stage 3 · Preference training

Show the model two responses to the same prompt and have a human indicate which is better.
Collect a great many such comparisons, train a model to predict those preferences, then use
that to further tune the assistant.

This is where nuance lives: helpfulness, honesty, tone, appropriate hedging, knowing when to
ask a clarifying question rather than guess.

It also introduces its own failure modes, which are worth knowing because you'll see them:

- **Sycophancy.** Humans rate agreement highly, so models drift toward agreeing with you.
  If you assert something false and ask the model to confirm, it is more likely to agree
  than it should be. **Watch for this when you use a model to check your own work.**
- **Verbosity.** Longer answers often get rated as more thorough, so models trend long.
- **Over-hedging.** Trained caution can become unhelpful waffle.

### Where "thinking" comes from

Newer models are additionally trained to produce extended reasoning before answering — to
work through a problem rather than emit an answer immediately.

The mechanical reason this helps is beautiful in its simplicity: **the model does a fixed
amount of computation per token.** A hard problem answered in one token gets one token's
worth of computation. The same problem worked through across 500 reasoning tokens gets 500
times more.

Reasoning tokens are *computation you're buying*. That's why extended thinking improves hard
problems and does nothing for easy ones, and why it costs more — you are literally paying
for more forward passes.

In current APIs you enable this with adaptive thinking and steer its depth with an effort
setting rather than a fixed token budget. You'll wire it up in Chapter 6.

---

## 5.10 · What the model does not have

Most beginner mistakes come from assuming one of these. Each absence is precise, and each
has an engineering answer later in this book.

### No memory

The API is **stateless**. The model does not remember your previous message. When a chat
feels continuous, it's because the application is resending the entire conversation every
single time.

```python
# Turn 1 sends:
[{"role": "user", "content": "My name is Ikram"}]

# Turn 2 sends the WHOLE history again:
[{"role": "user",      "content": "My name is Ikram"},
 {"role": "assistant", "content": "Nice to meet you, Ikram!"},
 {"role": "user",      "content": "What's my name?"}]
```

Two consequences that will shape your systems: conversations get **more expensive with every
turn**, because you resend everything; and eventually they exceed the context window, at
which point you must summarise, truncate, or compact. That's Chapter 18.

### No access to anything

No internet. No filesystem. No database. No clock. It cannot run the code it writes. It
produces text, and text alone. Everything else is a **tool you provide** — Part IV.

### No knowledge of itself

Ask a model how many parameters it has, what its context window is, or what today's date is,
and it will answer — from patterns in its training data, which may be stale or simply about
a different model. **Never trust a model's claims about its own configuration.** Read the
provider's documentation or query the models endpoint.

### No genuine uncertainty signal

It can *say* "I'm not sure," and post-training has made this much better. But the phrase is
generated the same way every other phrase is. Treat expressed confidence as weak evidence,
not as a calibrated probability.

### No guaranteed consistency

Same prompt, different answers — different phrasings, sometimes different substance. At
temperature 0 this narrows dramatically but never vanishes entirely. **Design for a
distribution of outputs, not a value.** This is the mindset shift from Chapter 1, arriving
with a mechanism attached.

---

## 5.11 · The context window

The context window is everything the model can see at once: system prompt, full conversation
history, retrieved documents, tool definitions, tool results, and the response being
generated. Measured in tokens.

Current models vary widely — some offer around 200K tokens, others up to 1M. A million
tokens is roughly 750,000 words, comfortably more than most books.

### Bigger is not automatically better

This surprises people, and it's important:

**1 · It costs more.** You pay per input token on every request. Resending 500K tokens each
turn is ruinous, and it's *why* prompt caching exists (Chapter 9).

**2 · It's slower.** Attention is quadratic. Long contexts increase time to first token
noticeably.

**3 · Attention gets diluted.** With 500,000 tokens competing for attention, the signal from
any one passage is weaker. More context can mean *less* focus on the part that mattered.

**4 · "Lost in the middle."** This is the one to remember. Across many models and many
studies, information placed at the **beginning** or **end** of a long context is recalled
substantially more reliably than information in the **middle**.

```
    Recall reliability across a long context

    high │█                                           █
         │██                                         ██
         │ ███                                     ███
         │   ████                               ████
    low  │      ████████████████████████████████
         └────────────────────────────────────────────
          start            middle                  end
```

Practical consequences you will actually use:

- Put the most important material **first or last**, not buried.
- Put the user's actual question **at the end**, after the retrieved context.
- **Don't paste everything because you can.** Retrieving the right 2,000 tokens usually
  beats supplying 200,000 and hoping.

> That last point is the strategic argument for Part III. Retrieval isn't a workaround for
> small context windows any more. It's a *quality* technique: giving the model less, but
> better, material reliably outperforms giving it everything.

### Input versus output

The context window is the total budget. `max_tokens` caps only the *response*, and it comes
out of the same budget.

A trap worth avoiding: setting `max_tokens` too low truncates the answer mid-sentence, and
you pay for the truncated output *and* the retry. Set it generously — and note that very
large values require streaming, because a non-streaming request that takes many minutes will
simply hit an HTTP timeout.

---

## 5.12 · A capability map

Everything here follows from the mechanism. That's the point — you should be able to
*predict* most of this table from what you now know.

### Reliably good at

| Capability | Why the mechanism supports it |
|---|---|
| Transforming text — summarise, rewrite, translate, reformat | Source material is in the context; this is copying and restructuring, not recall |
| Extracting structure from prose | Pattern recognition over visible text |
| Writing idiomatic code | Enormous, highly-patterned training data |
| Explaining concepts | Vast exposure to explanatory writing |
| Classifying and routing | A short, constrained output space |
| Drafting anything | Fluency is the core competence |

### Unreliable at

| Weakness | Mechanical reason |
|---|---|
| Precise arithmetic | Numbers are fragmented tokens; no place-value machinery |
| Character-level operations | It cannot see characters |
| Counting anything | No iteration, no counter, no state |
| Recent events | Frozen at the knowledge cutoff |
| Your private data | Never in the training set |
| Exact quotation from memory | Reconstructs plausibly rather than retrieving verbatim |
| Calibrated confidence | No uncertainty is computed |
| Very long multi-step logic | Errors compound; one wrong token poisons the rest |

### The pattern

Look at the two lists together and a rule emerges:

> **Models are strong when the information is in front of them, and weak when they must
> recall or compute it.**

That single sentence is the design principle for everything you'll build:

- Weak at recall → **put the facts in the context** (RAG, Part III)
- Weak at computation → **give it a calculator** (tools, Part IV)
- Weak at long chains → **break the task into steps** (workflows and agents, Part IV)
- Weak at self-assessment → **measure it externally** (evals, Part V)

The rest of this book is those four responses, worked out in detail.

---

## 5.13 · Experiments

No API key needed for the first two — use any chat interface you have. Do them; they take
under an hour and they teach more than re-reading will.

**1 · Break the tokenizer.** Search for a tokenizer visualiser and paste in: a normal
English sentence; the same sentence in another language; a long technical word; a JSON blob;
a code snippet; some emoji. Record the token count for each. **Then compute what 10,000
requests of each would cost** at the rates in Chapter 9. The non-English result should
bother you.

**2 · Hunt a hallucination.** Ask a model about something specific and obscure enough to be
uncertain but checkable — a minor function in a niche library, a detail from a small
open-source project. Then *verify it*. Note how confident the wrong answer sounded. Ask
again in a fresh conversation and see whether it invents the *same* falsehood or a different
one. That difference tells you something about which failure you're seeing.

**3 · Feel the temperature.** Same prompt, five fresh conversations, at temperature 0 and at
1 if your interface allows it. Try both a factual question and a creative one. Watch how
differently the two kinds of task respond.

**4 · Trigger the ratchet.** Get a model to make a small factual error, then ask follow-up
questions that assume the error is true. Watch it elaborate on its own invention. This is
section 5.8's second mechanism, live, and seeing it once makes you permanently suspicious of
long unverified outputs.

**5 · Test the lost-in-the-middle effect.** Take a long document — several thousand words.
Hide a distinctive sentence near the start, then in the middle, then near the end. Ask about
it each time. This is the single most useful experiment in the chapter, because it changes
how you'll lay out every prompt from here on.

**6 · Buy computation.** Ask a hard multi-step reasoning question two ways: demanding an
immediate answer, and asking it to work through the problem step by step first. Compare
accuracy. You just measured the value of spending more forward passes on a problem.

---

## 5.14 · Checkpoint

> **Move on to Chapter 6 when you can do all of these.**

**Explain to another engineer, without notes:**

1. What an LLM does, in one sentence, mechanically.
2. What a token is, and three practical consequences of subword tokenization.
3. What attention does, using the trophy/suitcase sentence.
4. Why "strawberry" defeats letter counting — mechanically, not as a quirk.
5. Why hallucinations are fluent and confident rather than hesitant and vague.
6. What temperature actually changes, and why it isn't a creativity dial.
7. Why a conversation gets more expensive with every turn.
8. Why a bigger context window doesn't automatically produce better answers.
9. Why "think step by step" improves hard problems — in terms of computation per token.

**Explain to a non-technical friend:**

10. Why an AI can write a working program but miscount the letters in a word. If they
    genuinely get it, you understand this chapter. This is the same test as Chapter 1, and
    it's still the best one there is.

**Predict, then verify:**

11. Given the mechanism, predict three tasks a model will be unreliable at — *without*
    looking at section 5.12. Then test your predictions against a real model.

**Complete:**

12. All six experiments, with your observations written in `PROGRESS.md`.

---

## 5.15 · Going deeper (optional)

**[Appendix A · The Mathematics of Attention](../../appendices/A-attention-maths.md)** — the actual equations,
with every symbol explained. Read it if you're curious; skip it without guilt. Nothing later
in this book requires it.

**If you want one paper:** *"Attention Is All You Need"* (Vaswani et al., 2017). You'll
understand perhaps half of it now, and that half is the half that matters. Revisit after
Appendix A.

**If you want to build one:** search for Andrej Karpathy's "Let's build GPT from scratch"
video. Three hours, from nothing to a working small transformer. The single best use of
three hours in this entire field, and it will make everything in this chapter concrete in a
way reading cannot.

**If you want to see inside a model:** search for "mechanistic interpretability" and
"induction heads." Researchers have identified specific circuits inside transformers
performing specific algorithms. It's the closest thing to reading a model's source code, and
it's genuinely thrilling.

**If you want the scaling story:** look up the Chinchilla scaling paper. It explains *why*
models are the sizes they are and how compute, data and parameters trade off — and it makes
a lot of industry news suddenly legible.

---

<div align="center">

**[← Project A](../../part-1-foundations/project-a-typed-api/)** · **[The Book](../../readme.md)** · **[Chapter 6 → Talking to Models](../ch06-talking-to-models/)**

*Chapter 5 of 31 · Week 5 · Part II begins*

</div>
