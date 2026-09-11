# Chapter 29 · Multimodal

### Vision, voice, and the latency budget that makes or breaks a conversation

> **Week 28, part 2 · ~11 hours**
>
> Two capabilities that change what you can build. Vision quietly fixes the worst problem in
> Part III; voice is a real-time systems problem wearing an AI costume.

---

## 29.0 · Why this chapter exists

Two things are worth your attention here, and they're worth it for different reasons.

**Vision solves a problem you already have.** Section 11.2 told you that PDF extraction is lossy
and hard — multi-column text interleaved, tables destroyed, scanned pages yielding nothing. A
model that can *see* the page sidesteps the entire extraction problem. This is the highest-value
multimodal application for most application engineers, and it's not the one people think of.

**Voice is where AI products are heading**, and it's mostly a latency engineering problem. Your
Flutter background gives you a real advantage here, which Chapter 30 develops.

---

## 29.1 · Vision

Images go into the context alongside text:

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    messages=[{"role": "user", "content": [
        {"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": b64_image,
        }},
        {"type": "text", "text": "Extract every line item from this invoice as JSON."},
    ]}],
)
```

Put the image **before** the text instruction — the model reads in order, and you want it to have
seen the image when it reads the question.

### What it's reliably good at

- **Reading documents** — layout, tables, forms, handwriting. The big one.
- Describing scenes and objects
- Reading charts and extracting approximate values
- Understanding diagrams and flow
- Reading UI screenshots — which is how visual regression and UI-testing agents work

### What it's unreliable at

- **Precise spatial reasoning** — exact coordinates, precise measurements
- **Counting** many objects — section 5.12's counting weakness, in a new modality
- Very small text, or text at low resolution
- Fine-grained visual comparison between two images

### The cost

Images consume tokens roughly in proportion to their area. A rough shape:

```
   tokens  ≈  (width × height) / 750
```

```
   512 × 512      ≈   350 tokens
  1024 × 1024     ≈  1,400 tokens
  1568 × 1568     ≈  3,300 tokens
```

**Two consequences:** a 20-page PDF sent as page images is expensive, so measure before you build
a pipeline on it. And **resize deliberately** — most document tasks work fine at moderate
resolution, and sending a 4000px scan wastes most of its tokens on detail the task doesn't need.
Find your minimum by measuring accuracy as you reduce resolution.

### Vision for document ingestion

This is the section that matters for your existing work.

```
   TEXT EXTRACTION (Ch 11)          VISION EXTRACTION
   ────────────────────             ─────────────────
   pdf → text layer → chunks        pdf → page images → model → markdown → chunks

   ✗ columns interleaved            ✓ reading order understood
   ✗ tables destroyed               ✓ tables preserved as markdown
   ✗ scanned pages empty            ✓ works on scans
   ✓ fast and cheap                 ✗ slower, more expensive
   ✓ exact character offsets        ✗ offsets must be reconstructed
```

**The pragmatic architecture is hybrid:** text extraction by default, vision as a fallback for
pages that fail. You already have the detector — section 11.2's `extraction_warnings` flags pages
with no text layer and tables that didn't parse. Route exactly those pages to vision.

That's a small change to a pipeline you've already built, and it recovers the documents you were
silently dropping.

### Multimodal retrieval

Two approaches, and the second is usually better:

**1 · Embed images directly** with a model trained on image/text pairs. Enables "find the diagram
showing the auth flow."

**2 · Describe, then embed the description.** Generate a text description with a vision model,
embed that. **Usually better for documents**, because your existing hybrid search, reranking and
citation machinery all work unchanged — and a good description is more searchable than an image
embedding.

---

## 29.2 · Voice

Three components, and the interesting part is the budget between them.

```
   speech  ──▶ [ STT ] ──▶ text ──▶ [ LLM ] ──▶ text ──▶ [ TTS ] ──▶ speech
              transcribe          generate           synthesise
```

### The latency budget

Natural conversation tolerates roughly **500ms** of silence before it feels broken. Sub-300ms
feels genuinely responsive. Above about a second, people start talking over it.

```
   silence detected (end of turn)      ~200ms   ← unavoidable; you must
                                                  wait to know they stopped
   STT final transcript                ~150ms
   LLM time to first token             ~400ms
   TTS first audio chunk               ~150ms
   ─────────────────────────────────────────
   first sound back                    ~900ms   ← too slow
```

Every technique you have applies, and two are specific to voice:

| Lever | Effect |
|---|---|
| **Streaming STT** | Transcribe as they speak; the final chunk arrives almost immediately |
| **Start generating on partial transcript** | Begin before they've finished, on a confident prefix |
| **Streaming TTS** | Synthesise the first sentence while the model writes the second |
| **Lower effort / smaller model** | Chapter 9 and 25 |
| **Prompt caching** | The system prompt and history are stable |
| **Sentence-boundary chunking for TTS** | Don't wait for the full response |

**Streaming everything is not an optimisation here — it's the architecture.** With all three
stages streaming and overlapping, sub-500ms is achievable.

### The hard parts aren't the models

The models are the easy part. These are the problems:

**Turn-taking.** Knowing when the user has finished. Voice activity detection plus a silence
threshold gets you most of the way; the threshold is a genuine tradeoff between cutting people
off and feeling sluggish.

**Interruption (barge-in).** A user talking over the assistant must stop it immediately —
including stopping the TTS mid-word and abandoning the in-flight generation. This is the single
biggest difference between a voice product that feels alive and one that feels like an IVR
system, and it's pure engineering.

**Context of what was actually heard.** The user heard only the part that played before they
interrupted. **Your conversation history must record what was *spoken*, not what was
generated**, or the model will reference things the user never heard.

That last one is subtle and it's the bug that makes voice assistants feel confusing.

**Transcription errors.** STT makes mistakes, especially with names, jargon and accents. The
model must handle garbled input gracefully — and a domain vocabulary hint to the STT system helps
more than anything downstream.

**Environment.** Noise, echo, multiple speakers, poor microphones.

---

## 29.3 · Image generation

Briefly, because it's a different discipline and rarely part of an application engineer's core
work.

You'll encounter it for illustration, product imagery and design tooling. The engineering
concerns that transfer: it's slow (seconds to tens of seconds, so async and streaming progress),
it's expensive per image, prompts behave differently from language-model prompts, and **content
safety and provenance matter more** — know what your provider does about both.

If you need it, the patterns from Chapters 4, 9 and 23 all apply: background jobs, cost tracking,
tracing.

---

## 29.4 · Build it

Two projects. **The first improves a system you already own.**

### 1 · Vision fallback for your ingestion pipeline

```
src/genai_toolkit/ingestion/extractors/vision.py
```

Requirements:

1. Detect pages that fail text extraction — no text layer, failed tables — using the
   `extraction_warnings` you already emit.
2. Render those pages as images at a resolution you've **measured**, not guessed.
3. Extract to markdown with a vision model, preserving tables.
4. Reconstruct character offsets so your Chapter 11 offset-fidelity test still passes. *(This is
   the genuinely hard part.)*
5. **Measure**: extraction quality, cost per page, and the effect on your Chapter 14 retrieval
   metrics.
6. Report how many previously-lost documents you recovered.

That last number is the headline. **"Recovered 12 documents that were silently dropped"** is a
concrete, checkable improvement to a system you built six weeks ago.

### 2 · A voice loop

```
src/genai_toolkit/voice/
├── stt.py          streaming transcription
├── tts.py          streaming synthesis
├── turn.py         VAD, silence detection, barge-in
└── loop.py         the conversation, fully streamed
```

Requirements:

1. **All three stages streaming and overlapping.**
2. **Measure your end-to-end latency budget** — decompose it like section 29.2.
3. **Barge-in that actually works** — stops TTS mid-word and cancels the in-flight generation.
4. **History records what was spoken, not what was generated.**
5. Graceful handling of a garbled transcript.
6. Get first-sound-back under **600ms**, and report your decomposition.

### The experiments

**1 · Resolution sweep.** Extract the same document at four resolutions. Plot accuracy against
token cost. **Find your minimum viable resolution** — it's usually lower than you'd assume.

**2 · Vision versus text extraction.** On 20 messy PDFs. Compare quality, cost and downstream
retrieval metrics. Decide your routing rule.

**3 · The voice waterfall.** Measure each stage. Cut 300ms. Say which stage and how.

**4 · Barge-in correctness.** Interrupt mid-sentence, then ask a follow-up referencing what you
*heard*. Does the model know what was actually spoken?

**5 · Transcription robustness.** Feed deliberately garbled transcripts. Does the system ask for
clarification, or confidently answer the wrong question?

---

## 29.5 · Checkpoint

> **Move on to Chapter 30 when all of these are true.**

**Explain, out loud:**

1. Why vision is the pragmatic fix for the PDF extraction problem from Chapter 11.
2. How image tokens scale, and why resizing is a real cost lever.
3. Why describe-then-embed usually beats direct image embedding for documents.
4. The voice latency budget, and which levers move which stage.
5. Why streaming all three stages is the architecture, not an optimisation.
6. Why conversation history must record what was **spoken**.
7. Why barge-in is the difference between a voice product and an IVR system.

**Verify:**

8. Your ingestion pipeline routes failed pages to vision, and offsets still pass.
9. You can state how many documents that recovered.
10. You have a measured resolution/accuracy curve.
11. A voice loop under 600ms first-sound, with the decomposition.
12. Barge-in works, and history reflects what was heard.

---

## 29.6 · Going deeper (optional)

**Read your provider's vision documentation** for exact token formulas, size limits and supported
formats. The details matter for cost.

**If documents are your domain:** look into document layout analysis models — they understand
page structure before extraction and are substantially better on hard documents than either text
scraping or naive vision.

**If voice interests you:** read about voice activity detection and turn-taking research. The
human conventions around turn-taking are more subtle than a silence threshold, and the products
that feel best model more of them.

**If you want the frontier:** read about end-to-end speech models that skip the STT/TTS
round-trip entirely. They collapse the latency budget and change the architecture — worth knowing
where things are heading.

---

<div align="center">

**[← Chapter 28](../ch28-local-models/)** · **[The Book](../../readme.md)** · **[Chapter 30 → Your Flutter Edge](../ch30-flutter-edge/)**

*Chapter 29 of 31 · Week 28*

</div>
