# Appendix B · Vector Mathematics

### Pairs with [Chapter 10](../part-3-retrieval/ch10-embeddings-deeply/)

> **Optional.** Chapter 10 told you to use cosine similarity. This explains why it works, why
> normalising lets you use the dot product instead, and why high-dimensional space behaves in
> ways that will otherwise surprise you.

---

## B.1 · A vector is a direction and a length

```
    v = [3, 4]
```

In two dimensions you can draw it — an arrow from the origin to the point (3, 4).

```
        ▲
      4 │      ● v = [3,4]
        │    ╱
        │  ╱   length = 5
        │╱
        └──────────▶
             3
```

An embedding is the same thing with 1,024 numbers instead of 2. You can't draw it, and every
operation below works identically regardless of how many dimensions there are.

**Two properties:** a **direction** (which way it points) and a **magnitude** (how long it is).

For embeddings, **direction carries the meaning.** Magnitude usually encodes things you don't
care about — text length, token count, quirks of the model. That single fact is why cosine
similarity is the right tool.

---

## B.2 · Magnitude

The length of a vector, written `‖v‖`, is Pythagoras extended to any number of dimensions:

```
    ‖v‖  =  √(v₁² + v₂² + ... + vₙ²)
```

```
    v = [3, 4]
    ‖v‖ = √(9 + 16) = √25 = 5
```

Also called the **norm**, or the L2 norm.

---

## B.3 · The dot product

Multiply element by element, add the results:

```
    a · b  =  a₁b₁ + a₂b₂ + ... + aₙbₙ
```

```
    a = [1, 2, 3]
    b = [4, 5, 6]
    a · b = 4 + 10 + 18 = 32
```

Here's the fact that makes everything else work. The dot product also equals:

```
    a · b  =  ‖a‖ × ‖b‖ × cos(θ)
```

where `θ` is the angle between the two vectors.

**So the dot product blends two different things:** how aligned the vectors are (`cos θ`), and
how long they are (`‖a‖ × ‖b‖`).

For similarity we want only the first. So we divide the second out.

---

## B.4 · Cosine similarity

Rearranging the identity above:

```
                        a · b
    cos(θ)  =  ─────────────────────
                   ‖a‖ × ‖b‖
```

That's cosine similarity: **the dot product, with both magnitudes divided out.** What remains is
pure alignment.

```python
import numpy as np

def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### What the values mean

```
    cos(0°)   =  1.0     same direction
    cos(60°)  =  0.5
    cos(90°)  =  0.0     perpendicular — unrelated
    cos(180°) = -1.0     opposite
```

```
       1.0  ●───▶  ●───▶        identical direction

       0.0  ●───▶
            │
            ▼                   perpendicular

      -1.0  ●───▶  ◀───●        opposite
```

### A worked example

```
    "a small cat"  →  a = [0.8, 0.6, 0.1]
    "a kitten"     →  b = [0.7, 0.7, 0.2]

    a · b  =  (0.8×0.7) + (0.6×0.7) + (0.1×0.2)
           =  0.56 + 0.42 + 0.02  =  1.00

    ‖a‖  =  √(0.64 + 0.36 + 0.01)  =  √1.01  =  1.005
    ‖b‖  =  √(0.49 + 0.49 + 0.04)  =  √1.02  =  1.010

    cos  =  1.00 / (1.005 × 1.010)  =  0.985
```

Highly similar, as you'd hope.

---

## B.5 · Normalisation, and the shortcut

A **unit vector** has magnitude exactly 1. You make one by dividing a vector by its own length:

```
    v̂  =  v / ‖v‖
```

```
    v = [3, 4],  ‖v‖ = 5
    v̂ = [0.6, 0.8]
    ‖v̂‖ = √(0.36 + 0.64) = √1 = 1   ✓
```

Now look at what happens to cosine similarity when both vectors are already unit length:

```
                a · b           a · b
    cos(θ)  =  ─────────  =  ─────────  =  a · b
                ‖a‖‖b‖         1 × 1
```

**The division disappears. Cosine similarity becomes just the dot product.**

This is why section 10.3 told you to normalise once at index time and use dot products
everywhere: you get cosine semantics at dot-product speed, and dot products are what hardware is
built to do fast.

```python
# normalise once, at index time
vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

# then search is a single matrix multiplication
scores = vectors @ query_vector       # cosine similarity for every document
```

That one line scores a million documents in milliseconds.

---

## B.6 · Euclidean distance, and when it differs

Straight-line distance between two points:

```
    d(a, b)  =  √((a₁-b₁)² + (a₂-b₂)² + ... + (aₙ-bₙ)²)
```

Cosine cares only about direction. Euclidean cares about direction *and* magnitude.

```
    a = [1, 1]
    b = [10, 10]

    cosine(a, b)     =  1.0     ← identical direction
    euclidean(a, b)  ≈  12.7    ← far apart
```

For text embeddings, **that difference is usually noise you don't want.** Magnitude often tracks
text length rather than meaning, so two documents about the same topic at different lengths
should be similar — and cosine says they are.

**The useful relationship:** for unit vectors, the two are equivalent orderings.

```
    d²  =  ‖a‖² + ‖b‖² - 2(a·b)  =  1 + 1 - 2cos(θ)  =  2(1 - cos θ)
```

Euclidean distance decreases exactly as cosine similarity increases. **Ranking by one is
identical to ranking by the other** — which is why, once normalised, the choice of metric stops
mattering for retrieval.

---

## B.7 · Why high-dimensional space is strange

This section explains several things Chapter 10 asserted without justification.

### Everything is far from everything

In high dimensions, distances concentrate. Pick random points in 1,000 dimensions and the
nearest is barely nearer than the farthest.

The intuition: distance sums a contribution from every dimension. With 1,000 dimensions, each
pair of points has 1,000 chances to differ, and the differences average out. Everything ends up
at roughly the same middling distance.

**Consequences you've already met:**

- Absolute similarity scores mean little (section 10.4).
- Relative ordering is what carries information.
- Exact nearest-neighbour search gets expensive, and approximate search (Chapter 12) becomes the
  practical answer.

### Almost everything is perpendicular

Pick two random vectors in `d` dimensions. As `d` grows, `cos(θ)` between them approaches 0.

In 2D, two random vectors are at a "typical" angle. In 1,000D, they're almost certainly close to
perpendicular.

**This is good news for retrieval:** random unrelated things score near zero, so any meaningfully
high score is signal. It's also why a high-dimensional space can hold so many distinguishable
concepts — there's room for an enormous number of nearly-perpendicular directions.

### But real embeddings are not random

Actual embedding spaces are **anisotropic** — vectors bunch into a narrow cone rather than
spreading evenly.

```
    Random vectors in 1000-D:     similarities cluster near 0
    Real text embeddings:         similarities cluster near 0.6–0.8
```

**This is why "unrelated" text still scores 0.6** (section 10.4), and why a threshold calibrated
for one model is meaningless for another.

**The only correct approach is empirical:** measure the distribution on your own data with your
own model, and set thresholds from that. Section 10.9's exercise.

---

## B.8 · Dimensionality and storage

```
    storage per vector  =  dimensions × bytes per number

    1,024 dims × 4 bytes (float32)  =  4,096 bytes  ≈  4 KB
```

```
        1M vectors  ×  4 KB  =    4 GB
       10M vectors  ×  4 KB  =   40 GB
      100M vectors  ×  4 KB  =  400 GB
```

Plus the index structure — HNSW roughly 1.5–2× again (section 12.8).

**Quantization** reduces bytes per number:

```
    float32  →  4 bytes    baseline
    int8     →  1 byte     4× smaller
    4-bit    →  0.5 bytes  8× smaller
    binary   →  1 bit      32× smaller
```

Binary quantization is remarkable: reduce each number to a single bit (positive or negative), and
similarity becomes a **Hamming distance** — count the differing bits, which modern CPUs do in a
single instruction. Quality drops meaningfully on its own, which is why it's paired with
full-precision rescoring of the top candidates (section 12.2).

---

## B.9 · Going further

**If you want the geometry:** search for "concentration of measure" and "curse of
dimensionality." The results are genuinely counter-intuitive — in high dimensions, nearly all the
volume of a sphere is in a thin shell near its surface.

**If you want the linear algebra properly:** 3Blue1Brown's "Essence of Linear Algebra" series.
Visual, beautiful, and it makes matrix multiplication feel obvious rather than mechanical.

**If you want to see it:** reduce your own embeddings to 2D with UMAP or t-SNE and plot them.
Twenty minutes rotating your own corpus teaches intuition no reading will. *(One caution: these
projections distort distances heavily. They're for looking, not for measuring.)*

<div align="center">

**[← Appendices](README.md)** · **[Chapter 10 →](../part-3-retrieval/ch10-embeddings-deeply/)**

</div>
