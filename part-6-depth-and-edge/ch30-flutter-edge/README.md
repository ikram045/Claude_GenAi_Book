# Chapter 30 · Your Flutter Edge

### The part almost nobody else in this field can do

> **Week 29 · ~22 hours · Your differentiator**
>
> Everything before this chapter makes you competitive. This chapter makes you distinctive.
> There are a great many competent AI application engineers. There are very few who can also
> ship the app.

---

## 30.0 · The positioning argument

Look honestly at the market you're entering.

**Most AI engineers are backend engineers.** They build the API, hand it to a mobile team, and
hope. They have never thought about what a 14-second p99 does to a user on a train, what happens
when streaming text causes a layout reflow on every token, or how an approval dialog should work
on a phone.

**Most mobile engineers treat AI as a remote API.** They call an endpoint, show a spinner, render
the text. They don't know what's in the prompt, why the answer was wrong, or what it cost.

**You are about to be in both groups**, and the overlap is genuinely thin.

```
      AI application engineers          Mobile engineers
      ┌──────────────────────┐      ┌──────────────────────┐
      │                      │      │                      │
      │    RAG · agents ·    │  ╱───┼──╲   Flutter ·       │
      │    evals · prompts   │ │ YOU │  │  platform ·      │
      │    cost · tracing    │  ╲───┼──╱   UX · offline    │
      │                      │      │                      │
      └──────────────────────┘      └──────────────────────┘
```

Two concrete consequences:

**It's a hiring story.** *"I can build the retrieval system, measure it, deploy it, and ship the
app that uses it"* is a sentence very few candidates can say. It makes you the obvious hire for
any team building an AI product with a mobile surface — which is an increasing number of them.

**It's a product capability.** On-device inference, offline-first AI, and AI UX that handles
latency and failure gracefully are things most teams simply cannot build because nobody on them
knows both halves.

This chapter is that capability, made concrete.

---

## 30.1 · Three architectures

```
   1 · SERVER-SIDE                  2 · HYBRID                  3 · ON-DEVICE
   ┌─────────┐                   ┌─────────┐                  ┌─────────┐
   │   app   │                   │   app   │                  │   app   │
   │         │                   │  small  │                  │  model  │
   └────┬────┘                   │  model  │                  │         │
        │ everything             └────┬────┘                  └─────────┘
   ┌────▼────┐                        │ hard things only
   │  cloud  │                   ┌────▼────┐                  nothing leaves
   └─────────┘                   │  cloud  │                  works offline
                                 └─────────┘
```

| | Server-side | Hybrid | On-device |
|---|---|---|---|
| Quality | Best | Best where it matters | Limited |
| Latency | Network-bound | Instant for simple | Instant |
| Offline | ✗ | Degraded | ✓ |
| Privacy | Data leaves | Sensitive stays local | Nothing leaves |
| Cost per user | Ongoing | Reduced | ~Zero |
| App size | Small | +model | +model |
| Battery | Negligible | Moderate | Significant |

> **Hybrid is almost always the right answer**, and it's the one that requires knowing both
> halves — which is exactly why it's your edge. Route on-device for what a small model handles
> well; go to the cloud for what it doesn't.

---

## 30.2 · AI UX — what backend engineers get wrong

This section is worth more than the on-device section for most products, and it's the part your
existing skills already cover.

### 1 · Streaming is the product

Section 9.8 said streaming is the biggest perceived-quality lever. On mobile it matters more,
because network conditions are worse and users are less patient.

But **naive streaming on mobile has a specific failure mode**, and it's the thing that separates
a polished AI app from a janky one:

```dart
// ❌ Rebuilds and re-lays-out the entire text on every token.
//    At 40 tokens/second, that's 40 full reflows per second.
//    On a long response, the frame rate collapses and the scroll stutters.
StreamBuilder<String>(
  stream: tokenStream,
  builder: (context, snapshot) => MarkdownBody(data: accumulated),
);
```

Three fixes, in order of impact:

**Batch the updates.** Accumulate tokens and rebuild at a fixed cadence — 10–16 times a second is
visually indistinguishable from every token and is four times less work.

```dart
Stream<String> batched(Stream<String> tokens, {Duration every = const Duration(milliseconds: 80)}) async* {
  final buffer = StringBuffer();
  Timer? timer;
  // accumulate, emit on a timer, flush on close
}
```

**Don't re-parse markdown every frame.** Parsing markdown is expensive. Render the *stable* prefix
as parsed markdown and the still-arriving tail as plain text, then re-parse only when a block
completes.

**Isolate the repaint.** `RepaintBoundary` around the streaming region so the rest of the screen
isn't repainted with it.

**Keep the scroll anchored** at the bottom while streaming, but stop auto-scrolling the moment the
user scrolls up. Nothing is more annoying than being dragged back down while you're reading.

### 2 · Cancellation must be instant and real

A user who taps stop expects it to stop — and expects not to be charged for what they didn't
receive.

```dart
// The UI must cancel the request, not just hide the output.
final cancelToken = CancelToken();
// ...
onStop: () => cancelToken.cancel();
```

And on the server: `request.is_disconnected()` from section 4.10, so generation actually stops
and you stop paying for tokens nobody will read.

### 3 · Show uncertainty honestly

You know from Chapter 5 that models are confidently wrong. Your UI should not amplify that.

- **Show sources** — a tappable citation that opens the source is the single best trust mechanism,
  and you have them from Chapter 15.
- **Surface refusals clearly.** `INSUFFICIENT_CONTEXT` should render as a distinct, honest state,
  not as a failure.
- **Never show a self-assessed confidence score** (section 8.6.7). It isn't calibrated and it
  will be trusted.
- **Make regeneration one tap.** It's the cheapest fix for a bad answer.

### 4 · Design for failure, because mobile fails

| Failure | Good handling |
|---|---|
| Network lost mid-stream | Keep the partial response, offer retry, don't lose the conversation |
| Rate limited | "Busy — retrying in 10s", with a countdown. Not an error dialog |
| Slow first token | Show *what it's doing* — "searching documents…" — from section 25.4's status events |
| App backgrounded | Continue or resume cleanly; never lose a response in flight |
| Generation failed | The user's message must be preserved and re-sendable |

That last one is the one most apps get wrong, and it's the most infuriating.

### 5 · Optimistic and interruptible

The user's message appears instantly. The response streams in. The whole interaction is
cancellable at any point. This is ordinary good mobile practice, and it's exactly what most
AI apps built by backend teams don't do.

---

## 30.3 · Streaming SSE into Flutter

The client half of Chapter 4's server.

```dart
Stream<AiEvent> streamAnswer(String question, {CancelToken? cancel}) async* {
  final request = http.Request('POST', Uri.parse('$baseUrl/chat/stream'))
    ..headers['Content-Type'] = 'application/json'
    ..headers['Accept'] = 'text/event-stream'
    ..body = jsonEncode({'question': question});

  final response = await client.send(request);

  if (response.statusCode != 200) {
    throw AiException.fromStatus(response.statusCode);
  }

  final lines = response.stream
      .transform(utf8.decoder)
      .transform(const LineSplitter());

  await for (final line in lines) {
    if (!line.startsWith('data: ')) continue;      // blank lines separate events
    final payload = line.substring(6);
    if (payload == '[DONE]') return;
    yield AiEvent.fromJson(jsonDecode(payload));
  }
}
```

Three details that bite:

**The blank line between events.** Section 4.10, from the client side — your line splitter will
see empty lines, and they're delimiters, not data.

**Buffering proxies.** If you see the whole response arrive at once, it's almost certainly
infrastructure, not your code. `X-Accel-Buffering: no` on the server.

**Backgrounding.** iOS and Android suspend network activity when backgrounded. Decide: resume,
restart, or let the server finish and fetch the result. **Don't just lose it.**

### The state shape

If you've used Bloc or Riverpod, this is familiar territory — a streaming response is exactly the
state machine you've built a hundred times:

```dart
sealed class AnswerState {}
class Idle        extends AnswerState {}
class Searching   extends AnswerState { final String stage; }
class Streaming   extends AnswerState { final String text; final bool canCancel; }
class Complete    extends AnswerState { final String text; final List<Citation> sources; }
class Refused     extends AnswerState { final String reason; }
class Failed      extends AnswerState { final String message; final bool retryable; }
```

**Model refusal as its own state, not as a failure.** From section 15.7 — it's a legitimate
outcome and should look like one.

---

## 30.4 · On-device inference

### What's actually possible

```
   Phone RAM available to an app:   ~2–4 GB realistically
   Model at 4-bit quantization:     ~0.5 GB per billion parameters

   1B model  ≈ 0.5 GB   ✓ comfortable, fast
   3B model  ≈ 1.5 GB   ✓ workable on mid/high-end
   7B model  ≈ 3.5 GB   ⚠ high-end only, tight
  13B+                  ✗ not on a phone
```

**Realistic speed:** single-digit to low-tens of tokens per second on a modern phone, depending
on chip, model and quantization. Slower than a laptop by a wide margin, and fast enough for short
outputs.

Section 28.7's laptop benchmark was your baseline. **Expect a phone to be several times slower**,
and measure on a mid-range device, not your own flagship.

### What small on-device models are good for

| ✓ Good | ✗ Poor |
|---|---|
| Classification and routing | Complex reasoning |
| Extraction from short text | Long context |
| Rewriting, summarising short passages | Reliable tool use |
| Embeddings for local search | Broad factual recall |
| Autocomplete and suggestions | Anything needing accuracy on hard questions |

**That left column is exactly the cheap half of a hybrid router** (section 25.3). Which is the
point.

### Getting a model onto the device

Three routes, in rough order of practicality for Flutter:

**Platform ML runtimes via plugins** — the mobile-native inference stacks exposed through a
Flutter plugin. Least work; you inherit platform optimisations and hardware acceleration.

**llama.cpp via `dart:ffi`** — compile the native library, bind it from Dart. Most control, most
work, and genuinely portable across platforms. If you want a deep technical portfolio piece, this
is it.

**Platform channels to native code** — write the inference in Swift/Kotlin against the platform
ML framework, call it from Dart. A good middle ground, and it plays to platform-specific hardware
acceleration.

Whichever you pick, **wrap it behind the same `LLMClient` abstraction you've used since Chapter
6.** The router shouldn't know or care where inference happened.

### The constraints backend engineers have never thought about

**Memory pressure.** The OS will kill your app if it holds too much. Load the model lazily,
release it when backgrounded, and handle the reload. A model held in memory across a backgrounding
is how your app gets terminated.

**Thermal throttling.** Sustained inference heats the device, and the OS throttles. **Your
benchmark on a cold phone is not your real-world performance.** Measure after five minutes of
continuous use — the number will be worse, sometimes much worse.

**Battery.** Sustained inference is a heavy draw and users notice. Prefer short bursts. Consider
deferring heavy local work to when the device is charging.

**App size.** A 1.5 GB model cannot ship in your bundle. Download on first run, with progress,
resumability, and a clear explanation of why. Cache it properly and handle the user clearing
storage.

**Device fragmentation.** A mid-range Android phone from three years ago is not your test device.
**Detect capability and degrade** — fall back to cloud-only on devices that can't cope.

> **Every one of these is a thing you already know how to handle from Flutter**, and a thing most
> AI engineers have never encountered. That asymmetry is the chapter.

---

## 30.5 · The hybrid router

The architecture that makes on-device worth doing.

```dart
Future<Answer> route(String query, DeviceContext device) async {
  final complexity = await onDeviceClassifier.classify(query);   // ~30ms, local

  final canRunLocally = complexity == Complexity.simple
      && device.hasModel
      && !device.isThermallyThrottled
      && (device.isCharging || device.batteryLevel > 0.2);

  if (canRunLocally) {
    try {
      return await onDevice.answer(query).timeout(const Duration(seconds: 5));
    } on TimeoutException {
      // fall through — don't leave the user waiting on a slow device
    }
  }

  if (!await connectivity.isOnline) {
    return Answer.offline(await onDevice.bestEffort(query));
  }

  return await cloud.answer(query);
}
```

Note what the routing decision includes: **thermal state and battery level.** No backend engineer
would think to check those, and they're exactly what determines whether local inference is a good
experience right now.

**Measure the split**, the same way as section 25.3: per-route eval scores, so you know the
on-device path isn't quietly degrading a third of your answers.

---

## 30.6 · Offline-first AI

The capability that's genuinely hard to build without both skill sets — and a real product
differentiator.

```
   ONLINE                          OFFLINE
   full pipeline, cloud model      on-device model
   fresh corpus                    cached corpus subset
   all features                    core features, clearly marked
```

What it requires, and each piece is something you already know how to build:

**Local retrieval.** An on-device vector index over a cached subset of the corpus. SQLite with a
vector extension, or a simple flat index — your Chapter 10 NumPy store, in Dart. At a few thousand
chunks, brute force is fine on a phone.

**Sync.** Incremental corpus updates when connectivity returns. Your Chapter 12 content hashing
determines what changed.

**Queue.** Requests that need the cloud, queued and retried when online. A standard mobile pattern.

**Honest state.** The UI must say what's degraded. *"Offline — answering from 240 cached
documents, last updated Tuesday"* is trustworthy. Silently giving worse answers is not.

---

## 30.7 · Build it

**An AI-powered Flutter app over your Project C or E backend.** This is the centrepiece of your
capstone.

```
app/
├── lib/
│   ├── ai/
│   │   ├── client.dart          SSE streaming client
│   │   ├── events.dart          typed event model
│   │   ├── router.dart          on-device vs cloud
│   │   ├── local/               on-device inference + local index
│   │   └── state.dart           the sealed state machine
│   ├── ui/
│   │   ├── chat.dart            streaming, batched, repaint-isolated
│   │   ├── citations.dart       tappable sources
│   │   ├── approval.dart        for agent actions (Project D)
│   │   └── status.dart          offline, degraded, cost
│   └── main.dart
```

Requirements:

1. **Streaming SSE** with batched UI updates and no frame drops on a long response.
2. **Instant cancellation** that actually stops server-side generation.
3. **Tappable citations** opening the source.
4. **Refusal as a distinct state**, not an error.
5. **Every failure mode from 30.2 table 4** handled, including backgrounding mid-stream.
6. **On-device model** for at least one task — classification, or short-answer generation.
7. **Hybrid routing** including thermal and battery signals.
8. **Offline mode** with local retrieval over a cached corpus and honest UI state.
9. **Cost visibility**, if it's your own key.
10. Tested on a **mid-range device**, not just your own.

### The measurements — this is what makes it a portfolio piece

| | Measure |
|---|---|
| **Frame rate during streaming** | Target: 60fps sustained. Before and after batching |
| **Time to first token** | On wifi, on 4G, on slow 3G |
| **On-device tokens/second** | Cold, and after 5 minutes of sustained use |
| **Battery drain** | Per 100 on-device generations |
| **Route split** | % handled locally, with per-route eval scores |
| **Offline coverage** | % of your eval set answerable offline |
| **App size impact** | Bundle before and after |

**Nobody else has these numbers**, because nobody else is measuring both halves. A README with
that table is unusually convincing.

### Break it deliberately

1. Stream a 2,000-token response without batching. Watch the frame rate. **Then batch it and
   measure the difference.** This is the most instructive five minutes in the chapter.
2. Kill the network mid-stream. Is the partial response kept? Is the user's message preserved?
3. Background the app mid-generation. Return. What happened?
4. Run on-device inference for five minutes straight. Measure throughput before and after.
5. Fill the device's memory, then try to load the model. Does it fail gracefully?
6. Run on the oldest device you can find. Does it detect and degrade?

---

## 30.8 · Checkpoint

> **Move on to Chapter 31 when all of these are true.**

**Explain, out loud:**

1. The positioning argument — why this combination is rare and what it's worth.
2. The three architectures and why hybrid usually wins.
3. Why naive token-by-token rendering destroys frame rate, and three fixes.
4. Five mobile-specific constraints on local inference that backend engineers never meet.
5. Why thermal state and battery belong in a routing decision.
6. What offline-first AI requires, and why honest UI state is part of it.

**Verify:**

7. Streaming holds 60fps on a long response, measured before and after batching.
8. Cancellation stops server-side generation, verified in your traces.
9. On-device inference runs, with cold and sustained throughput both measured.
10. Hybrid routing works, with per-route eval scores.
11. Offline mode answers from a local index, with honest UI state.
12. Everything tested on a mid-range device.
13. **You have the measurement table from 30.7.**

Number 13 is the artefact. It's the thing that proves you measured both halves.

---

## 30.9 · Going deeper (optional)

**Read the mobile ML runtime documentation** for both platforms. Understanding what hardware
acceleration is available — and when it isn't — is what separates a working on-device feature
from a good one.

**Profile with Flutter DevTools** during streaming. Watch the frame timeline. You'll see the
reflow cost immediately, and the fix will be obvious.

**Look at the small-model families designed for on-device use.** They're a different design point
from the frontier models — optimised for size and speed rather than peak capability — and
understanding that tradeoff tells you what to route to them.

**If you want a distinctive open-source contribution:** a well-built Flutter package for on-device
LLM inference, or for streaming SSE with proper cancellation and backgrounding, would be genuinely
useful and genuinely visible. The ecosystem is thin here, and you are unusually well placed to
fill it.

---

<div align="center">

**[← Chapter 29](../ch29-multimodal/)** · **[The Book](../../readme.md)** · **[Chapter 31 → Portfolio & Positioning](../ch31-portfolio/)**

*Chapter 30 of 31 · Week 29 · Your edge*

</div>
