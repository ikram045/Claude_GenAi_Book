# Appendix A · The Mathematics of Attention

### Pairs with [Chapter 5](../part-2-language-models/ch05-what-an-llm-is/)

> **Optional.** Chapter 5 explained what attention *does* — every token looks at every other
> token and decides what's relevant. This explains what it *computes*.
>
> Every symbol is defined. If you can multiply numbers and add them up, you can follow this.

---

## A.1 · The three things you need

**A vector** is a list of numbers. We write it in square brackets.

```
    v = [2, 0, 1]
```

**A matrix** is a grid of numbers — a list of vectors stacked up.

```
        ┌ 1  0  2 ┐
    M = │ 3  1  0 │
        └ 0  2  1 ┘
```

**A dot product** takes two vectors of the same length, multiplies them element by element, and
adds the results into a single number.

```
    a = [1, 2, 3]
    b = [4, 5, 6]

    a · b  =  (1×4) + (2×5) + (3×6)  =  4 + 10 + 18  =  32
```

**The one intuition to carry:** the dot product measures **alignment**. Two vectors pointing the
same way give a large positive number. Two pointing in unrelated directions give something near
zero. Two pointing opposite ways give a large negative number.

That's it. Attention is built almost entirely from dot products.

---

## A.2 · The setup

Your input is a sequence of `n` tokens. Each has been turned into a vector of length `d` (section
5.3). Stack them and you get a matrix:

```
    X  has shape  (n × d)

    n = number of tokens        e.g. 12 tokens
    d = embedding dimension     e.g. 4096 numbers per token
```

Each **row** of `X` is one token's vector.

---

## A.3 · Query, key, value

From three learned matrices — `W_Q`, `W_K`, `W_V` — we produce three new matrices:

```
    Q = X · W_Q          the QUERIES   — "what am I looking for?"
    K = X · W_K          the KEYS      — "what do I offer?"
    V = X · W_V          the VALUES    — "what do I contribute?"
```

The `W` matrices are **learned during training**. They start random and are adjusted by the
training process until they produce useful queries, keys and values.

Each of `Q`, `K`, `V` has shape `(n × d_k)`, where `d_k` is the dimension of the attention head —
typically smaller than `d`.

**Row `i` of `Q`** is the query vector for token `i`. Same for keys and values.

---

## A.4 · The formula

Here it is, whole:

```
                          ┌       Q · Kᵀ     ┐
    Attention(Q, K, V) =  │ softmax ─────── │ · V
                          └        √d_k      ┘
```

Four steps. We'll take them one at a time.

### Step 1 · `Q · Kᵀ` — score every pair

`Kᵀ` means **K transposed** — flipped so its rows become columns. This lets us multiply `Q` by it.

```
    Q  is (n × d_k)
    Kᵀ is (d_k × n)
    Q · Kᵀ is (n × n)
```

The result is an `n × n` grid where **entry (i, j) is the dot product of token i's query with
token j's key.**

```
              key of →   The   trophy  doesn't   fit    ...
    query of ↓
    "it"                 0.2    4.7     0.1      0.8
```

From section A.1: a large dot product means those two vectors are aligned — the query is looking
for something, and that key advertises it. Token `"it"` is looking for a noun it can refer to,
and `"trophy"` advertises exactly that, so the score is high.

**This single matrix multiplication compares every token to every other token.** That's the `n²`
cost from section 5.4.

### Step 2 · `÷ √d_k` — the scaling

Why divide by the square root of the head dimension?

Dot products of high-dimensional vectors get large. If each component is roughly the same size,
a dot product over `d_k` components grows roughly in proportion to `√d_k`.

Large numbers going into softmax (step 3) produce an extremely peaked output — almost all the
weight on one token, almost none elsewhere. During training, that makes gradients vanish and
learning stalls.

Dividing by `√d_k` keeps the numbers in a range where softmax stays well-behaved. **It's a
numerical stability fix, and it's why the operation is called *scaled* dot-product attention.**

### Step 3 · `softmax` — turn scores into weights

Softmax converts a row of arbitrary numbers into a row of probabilities: all positive, summing
to 1.

```
                        e^(xᵢ)
    softmax(x)ᵢ  =  ───────────────
                     Σⱼ e^(xⱼ)
```

Where `e` is Euler's number (≈ 2.718) and `Σⱼ` means "sum over all j."

Worked example:

```
    scores:        [2.0,  1.0,  0.1]

    e^2.0 = 7.39
    e^1.0 = 2.72
    e^0.1 = 1.11
    sum   = 11.22

    softmax:       [7.39/11.22,  2.72/11.22,  1.11/11.22]
                =  [0.659,       0.242,       0.099]
                                              (sums to 1.0)
```

**Two properties that matter:** exponentiating amplifies differences — a score of 2.0 versus 1.0
becomes a weight of 0.66 versus 0.24, a much bigger gap than the raw scores had. And everything
stays positive and sums to 1, so the result is a valid set of mixing weights.

Applied row by row, this turns the score grid into the attention weights you saw in section 5.4.

### Step 4 · `· V` — mix the values

```
    attention_weights  is (n × n)
    V                  is (n × d_k)
    result             is (n × d_k)
```

Row `i` of the result is a **weighted average of every token's value vector**, weighted by how
much token `i` attended to each.

```
    output_for("it")  =  0.01 × value("The")
                      +  0.62 × value("trophy")     ← dominates
                      +  0.02 × value("doesn't")
                      +  0.08 × value("fit")
                      +  ...
```

The representation of `"it"` is now mostly made of `"trophy"`. **The ambiguity has been resolved
by arithmetic.**

---

## A.5 · Multi-head attention

One set of `W_Q`, `W_K`, `W_V` captures one kind of relationship. Real language has many at once.

So run `h` attention operations in parallel, each with its own learned projections:

```
    head₁ = Attention(X·W_Q¹, X·W_K¹, X·W_V¹)
    head₂ = Attention(X·W_Q², X·W_K², X·W_V²)
    ...
    head_h = Attention(X·W_Q^h, X·W_K^h, X·W_V^h)

    MultiHead(X) = concat(head₁, ..., head_h) · W_O
```

`concat` glues the outputs side by side; `W_O` is one more learned matrix that mixes them back
into shape `d`.

Each head is free to specialise, and interpretability research has found heads that appear to
track grammatical dependencies, coreference, quotation, and copying from earlier text.

Typically `d_k = d / h`, so the total computation is roughly the same as one full-width head.

---

## A.6 · Causal masking

A model generating text must not see the future. When predicting token 5, it may look at tokens
1–4 and not at 6 onward.

This is enforced by **masking**: before the softmax, set every score where `j > i` to negative
infinity.

```
    ┌  s₁₁   -∞    -∞    -∞  ┐
    │  s₂₁   s₂₂   -∞    -∞  │
    │  s₃₁   s₃₂   s₃₃   -∞  │
    └  s₄₁   s₄₂   s₄₃   s₄₄ ┘
```

Because `e^(-∞) = 0`, those positions get exactly zero weight after softmax. A token can attend
to itself and everything before it, and nothing after.

**This is why generation is autoregressive** (section 5.1) — the architecture enforces it.

---

## A.7 · The cost

```
    Q · Kᵀ           →  n × n × d_k  multiplications
    weights · V      →  n × n × d_k  multiplications
    ────────────────────────────────────────────────
    total            →  O(n² · d)
```

**Quadratic in sequence length.** Double the context and attention cost roughly quadruples.

```
    n = 1,000     →       1,000,000 pairwise scores
    n = 10,000    →     100,000,000
    n = 100,000   →  10,000,000,000
```

Memory is also `O(n²)` for the attention matrix, which for a long time was the harder limit.

**This one fact explains a great deal:** why context windows were small for years, why long
contexts cost more and run slower (section 9.8), why enormous engineering effort has gone into
cheaper attention variants — and, indirectly, why Part III exists. Retrieval is what you do
instead of paying `n²` on everything you own.

---

## A.8 · The whole layer

Attention is one half. A transformer layer is:

```
    ┌─────────────────────────────────────┐
    │  x  ──▶ LayerNorm ──▶ MultiHead ──┐ │
    │  │                                 │ │
    │  └──────────────── + ◀─────────────┘ │   ← residual connection
    │                    │                 │
    │  ──▶ LayerNorm ──▶ FeedForward ──┐   │
    │  │                                │   │
    │  └─────────────── + ◀─────────────┘   │   ← residual connection
    └─────────────────────────────────────┘
```

**LayerNorm** rescales each vector to have mean 0 and standard deviation 1, which keeps values in
a stable range as they pass through dozens of layers.

**FeedForward** is two matrix multiplications with a non-linearity between them, applied
independently at each position:

```
    FFN(x) = W₂ · activation(W₁ · x + b₁) + b₂
```

It's usually about four times wider in the middle than the input. **Most of a model's parameters
live here**, and there's good evidence this is where factual associations are stored (section
5.5). Attention moves information between positions; feed-forward layers process it.

**The `+` arrows are residual connections** — each block *adds* its output to its input rather
than replacing it. This is the shared whiteboard from section 5.5, and it's what makes very deep
networks trainable at all: the gradient has a direct path back through the additions.

Stack this block dozens of times and you have a transformer.

---

## A.9 · Going further

**The paper:** "Attention Is All You Need" (Vaswani et al., 2017). You can now read section 3.2
and recognise every symbol.

**The implementation:** Andrej Karpathy's "Let's build GPT from scratch" — three hours from
nothing to a working transformer. **This appendix plus that video is the fastest route to real
understanding**, because you'll write the formula you just read.

**The frontier:** search for FlashAttention (making `n²` cheaper in practice through better
memory access) and linear attention variants (making it not `n²` at all, with tradeoffs).

<div align="center">

**[← Appendices](README.md)** · **[Chapter 5 →](../part-2-language-models/ch05-what-an-llm-is/)**

</div>
