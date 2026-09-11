# Appendix C · How Fine-Tuning Actually Works

### Pairs with [Chapter 27](../part-6-depth-and-edge/ch27-fine-tuning/)

> **Optional.** Chapter 27 told you LoRA trains "small adapters" holding roughly 0.1% of the
> parameters. This explains what that means, why it works, and what the hyperparameters are
> actually doing.

---

## C.1 · Training is finding the bottom of a valley

A model has parameters — billions of numbers. Training adjusts them so the model's predictions
get better.

"Better" needs a number. That number is the **loss**: how wrong the model was.

For next-token prediction, it's **cross-entropy loss**:

```
    L  =  -log( p(correct token) )
```

Where `p(correct token)` is the probability the model assigned to the token that actually came
next.

```
    model said the correct token had probability 0.9   →  L = -log(0.9) = 0.105   good
    model said                                  0.5    →  L = -log(0.5) = 0.693
    model said                                  0.1    →  L = -log(0.1) = 2.303   bad
    model said                                  0.01   →  L = -log(0.01) = 4.605  very bad
```

**Confident and right is cheap. Confident and wrong is expensive.** That asymmetry is what
pushes the model toward calibration.

Now picture the loss as a landscape. Each parameter is a direction you can move in; the height is
the loss. **Training is walking downhill.**

With billions of parameters the landscape has billions of dimensions, which you cannot picture —
but the algorithm doesn't need you to.

---

## C.2 · Gradient descent

A **gradient** tells you, for each parameter, which way is uphill and how steeply.

```
    ∂L/∂w   "if I nudge parameter w slightly, how much does the loss change?"
```

If that's positive, increasing `w` increases the loss — so decrease it. If negative, do the
opposite. Formally:

```
    w_new  =  w_old  -  η × (∂L/∂w)
```

Where `η` (eta) is the **learning rate** — how big a step to take.

```
       loss
        │╲
        │ ╲    ● ← you are here; the gradient points uphill
        │  ╲  ╱
        │   ╲╱     step downhill by η × gradient
        │    ▼
        └──────────▶ parameter value
```

### Why the learning rate is the parameter that matters most

```
    too small  →  ● ▸ ▸ ▸ ▸ ▸ ▸ ▸ ▸    barely moves; training stalls

    about right → ●  ▸▸  ▸▸  ▸▸ ▼       converges

    too large  →  ●────────▶  ◀────────  overshoots, oscillates,
                                          or diverges entirely
```

For fine-tuning specifically, the learning rate has an extra job: **too high and the model
forgets what it already knew** — catastrophic forgetting (section 27.2). You're trying to nudge a
model that's already good, not retrain it.

That's why fine-tuning learning rates (around 1e-4 for LoRA) are far smaller than pretraining
ones.

---

## C.3 · Backpropagation, in one idea

To take a step you need `∂L/∂w` for every parameter. In a network with a hundred layers, how do
you know how much a parameter in layer 3 contributed to the final loss?

**The chain rule.** If `a` affects `b`, and `b` affects `c`, then:

```
    ∂c/∂a  =  (∂c/∂b) × (∂b/∂a)
```

Backpropagation applies this repeatedly, working *backwards* from the loss through every layer.
Each layer computes how much its inputs contributed, using the gradient handed back from the
layer above.

```
    forward   →  →  →  →  →  →  →  loss
    backward  ←  ←  ←  ←  ←  ←  ←
```

**This is why training needs so much memory.** The backward pass needs the activations from the
forward pass, so they must all be held. For a large model with a large batch, that dominates
memory use — more than the weights themselves.

It's also the main thing LoRA avoids paying for.

---

## C.4 · Why full fine-tuning is expensive

Training a model needs memory for four things:

```
    weights              1× model size
    gradients            1× model size     (one per parameter)
    optimizer state      2× model size     (Adam keeps two running averages)
    activations          depends on batch and sequence length
    ─────────────────────────────────────
    total               ≈ 4× model size, plus activations
```

```
    A 7B model at fp16:
      weights            14 GB
      gradients          14 GB
      optimizer state    28 GB
      ──────────────────────
      ≈ 56 GB before activations
```

**That's why full fine-tuning of even a small model needs serious hardware**, and why an
alternative was worth inventing.

---

## C.5 · The low-rank insight

Here's the observation LoRA is built on.

When you fine-tune, the *change* to each weight matrix is `ΔW`:

```
    W_finetuned  =  W_pretrained  +  ΔW
```

`ΔW` has the same shape as `W` — for a 4096 × 4096 matrix, that's 16.8 million numbers.

**But the update doesn't need that much freedom.** Empirically, the changes fine-tuning makes are
**low-rank** — they can be closely approximated by the product of two much smaller matrices.

### What "rank" means

The rank of a matrix is the number of genuinely independent directions in it.

```
        ┌ 1  2  3 ┐
    M = │ 2  4  6 │        Row 2 = 2 × Row 1
        └ 3  6  9 ┘        Row 3 = 3 × Row 1

    Three rows, but only ONE independent direction.  rank(M) = 1
```

A rank-1 matrix, however large, is just one vector times another:

```
    M  =  [1, 2, 3]ᵀ × [1, 2, 3]
```

Three numbers and three numbers describe all nine. The same principle scales.

### The decomposition

Instead of learning `ΔW` directly, LoRA learns two thin matrices:

```
    ΔW  ≈  B · A

    A  is (r × d)      r is the RANK — small, e.g. 8 or 16
    B  is (d × r)
```

Their product `B · A` has shape `(d × d)` — the same as `ΔW` — but is constructed from far fewer
numbers.

```
    ΔW directly:   4096 × 4096            =  16,777,216 parameters
    B · A at r=8:  (4096×8) + (8×4096)    =      65,536 parameters

                                             0.39% of the size
```

### The forward pass

```
    h  =  W·x  +  B·A·x
          └─┬─┘    └─┬─┘
          frozen   trained
```

`W` never changes. Only `A` and `B` do.

`A` is initialised randomly and `B` is initialised to **zero**, so `B·A = 0` at the start and the
model begins exactly as the base model did. Training then moves it away gradually — no
destructive first step.

### What this buys you

```
    Memory:     gradients and optimizer state only for A and B
                → roughly 0.4% of the full fine-tuning requirement

    Artefact:   adapters are megabytes, not gigabytes
                → dozens can be stored and swapped per request

    Speed:      far fewer parameters to update each step

    Safety:     the base model is untouched, so forgetting is limited
                by construction
```

### Choosing `r`

```
    r = 4–8      style, tone, output format
    r = 16–32    task-specific behaviour        ← the usual range
    r = 64–128   substantial behavioural change
```

**Higher isn't automatically better.** More rank means more capacity — including more capacity to
memorise your training set instead of learning its pattern. If validation loss turns upward
early, try a lower rank before you try more data.

### And `lora_alpha`

The adapter's output is scaled by `α / r`:

```
    h  =  W·x  +  (α/r) × B·A·x
```

`α` decouples the adapter's effective strength from its rank, so changing `r` doesn't require
re-tuning the learning rate. The common convention `α = 2r` keeps the scaling constant at 2.

---

## C.6 · QLoRA: quantize the frozen part

If `W` never changes, it doesn't need full precision.

```
    LoRA:    W frozen at fp16   (14 GB for 7B)  +  adapters trained at fp16
    QLoRA:   W frozen at 4-bit  (3.5 GB)        +  adapters trained at fp16
```

The base is quantized to 4 bits and dequantized on the fly during the forward pass. The adapters
stay at full precision, because they're the part that's learning.

**Result: a model you couldn't load at all now fine-tunes on one consumer GPU.**

The costs are real but modest: slightly lower quality from quantization error, and slower
training from the dequantization work on every forward pass.

---

## C.7 · Reading the training curves

```
   loss
    │╲
    │ ╲___________ training loss
    │      ╲______
    │   ___╱                  ← validation turns UP
    │  ╱
    └──────────────────▶ steps
              ▲
         stop here
```

**Training loss falling, validation loss rising** is the definition of overfitting: the model is
memorising your examples rather than learning the pattern in them.

This is why section 27.5 says 1–3 epochs. Beyond that you're usually memorising.

**Other shapes and what they mean:**

| Shape | Likely cause |
|---|---|
| Both plateau high | Learning rate too low, or the pattern isn't in your data |
| Loss spikes and diverges | Learning rate too high |
| Loss near zero immediately | **Leakage** — your validation set is in your training set |
| Very noisy | Batch size too small |

**Checkpoint every epoch and keep the best *validation* checkpoint, not the last one.**

---

## C.8 · Going further

**The LoRA paper** (Hu et al., 2021). Short and clear. You can now read the method section and
recognise every term.

**The QLoRA paper** (Dettmers et al., 2023) for the quantization details, which are ingenious
beyond their application here.

**If you want the fundamentals properly:** 3Blue1Brown's neural network series for backpropagation
— the visual explanation of the chain rule is the best available.

**If you want to feel it:** fine-tune a very small model on a tiny dataset and watch the loss
curves live. Deliberately set the learning rate too high, then too low. Half an hour of that
teaches more about training dynamics than any amount of reading.

<div align="center">

**[← Appendices](README.md)** · **[Chapter 27 →](../part-6-depth-and-edge/ch27-fine-tuning/)**

</div>
