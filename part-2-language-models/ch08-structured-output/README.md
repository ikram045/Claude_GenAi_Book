# Chapter 8 · Structured Output

### Turning "a string you hope is JSON" into a typed object you can rely on

> **Week 8, part 1 · ~11 hours · Heavy code**
>
> The bridge between a language model and the rest of your program. Every pipeline, every
> agent, and every eval in Parts III–V crosses this bridge.

---

## 8.0 · Why this chapter exists

A model produces text. Your program needs data.

Everything between those two sentences is this chapter, and it is the single most common
place where beginner LLM applications break in production. Not because the concept is hard —
because the *failure modes* are subtle, intermittent, and invisible in a demo.

Here is the situation in one snippet:

```python
response = call_model("Extract the name and email from this text: ...")
data = json.loads(response)          # ← this line will fail in production
```

It works perfectly the first fifty times. Then one of these happens:

````
"Here's the extracted information:\n\n```json\n{...}\n```"     ← wrapped and introduced
'{"name": "Ada", "email": "ada@example.com",}'                 ← trailing comma
'{"name": "Ada"}'                                              ← field silently missing
'{"name": "Ada", "email": null}'                               ← null where you expected str
'{"name": "Ada", "confidence": 0.9, "email": "..."}'           ← bonus field you never asked for
"I couldn't find an email address in the provided text."       ← not JSON at all
````

Each is a `JSONDecodeError`, a `KeyError`, or — worst of all — a `None` that flows silently
into your database and surfaces as a bug three weeks later.

There is a real answer to this, and it is not "write a better regex." By the end of this
chapter, malformed output will be **impossible** rather than merely discouraged, and you'll
know what to do in the cases where it's still possible.

---

## 8.1 · Four levels of reliability

Understand these as a ladder. Most tutorials stop at level one; production lives at three and
four.

| Level | Technique | Reliability | Use when |
|:---:|---|---|---|
| 1 | Ask for JSON in the prompt | ~90–98% | Prototyping only |
| 2 | Ask + validate with Pydantic | Same, but failures are *caught* | Better, still not enough |
| 3 | **Schema-constrained output** | Guaranteed well-formed | ✅ The default |
| 4 | **Strict tool use** | Guaranteed well-formed | ✅ When it's an action, not a value |

Levels 3 and 4 are the same guarantee delivered through two different API surfaces. Which one
you pick depends on whether the model is *returning a value* or *calling a function*.

---

## 8.2 · Level 1 — asking, and why it isn't enough

```python
system = """Extract contact information.

Output only a JSON object matching:
{"name": string, "email": string, "company": string | null}

No markdown fences. No explanation. No preamble."""
```

This is genuinely much better than "respond in JSON" — it's Chapter 7's specificity principle
applied. It'll work the overwhelming majority of the time.

**And "overwhelming majority" is not a specification.** At 98% reliability and 10,000 requests
a day, that's 200 failures daily. In a pipeline, each one either crashes a job or writes
garbage.

If you're stuck at this level — an older model, a provider without schema support — at least
parse defensively:

```python
import json
import re

def extract_json(text: str) -> dict:
    """Best-effort JSON extraction. A fallback, never a foundation."""
    text = text.strip()

    # Strip markdown fences if present
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: find the outermost braces
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError(f"no JSON found in response: {text[:200]!r}")
```

Write it, keep it for emergencies, and understand that **every line of it is compensating for
a problem you can eliminate entirely.** Don't build on it.

---

## 8.3 · Level 2 — validate at the boundary

Parsing gives you a `dict`. A `dict` is not a contract — nothing guarantees `data["email"]`
exists or is a string.

Chapter 2 introduced Pydantic. This is where it earns its place.

```python
from pydantic import BaseModel, Field, ValidationError


class Contact(BaseModel):
    name: str = Field(min_length=1)
    email: str
    company: str | None = None


def parse_contact(raw: str) -> Contact | None:
    try:
        return Contact.model_validate_json(raw)
    except ValidationError as e:
        logger.warning("invalid contact payload: %s", e.errors())
        return None
```

What this changes: failures become **loud, immediate, and precisely located**. Instead of a
`None` propagating silently into your database, you get an error naming the exact field and
the exact reason, at the boundary where the data entered.

That's a genuine improvement, and it is still only *detection*. You've made failures visible;
you haven't made them rarer. For that, you need the model to be unable to produce them.

---

## 8.4 · Level 3 — schema-constrained output

This is the real answer, and it works differently from everything above.

Rather than *asking* for a shape and hoping, you attach a JSON Schema to the request. The
provider constrains generation itself: at each step, tokens that would produce invalid JSON
against your schema are not available to be sampled.

**Malformed output stops being unlikely and becomes structurally impossible.**

### The ergonomic form — `messages.parse()`

Define a Pydantic model, hand it over, get a validated instance back:

```python
from pydantic import BaseModel
import anthropic

client = anthropic.Anthropic()


class ContactInfo(BaseModel):
    name: str
    email: str
    plan: str
    interests: list[str]
    demo_requested: bool


response = client.messages.parse(
    model="claude-opus-5",
    max_tokens=16_000,
    messages=[{
        "role": "user",
        "content": "Extract: Jane Doe (jane@co.com) wants Enterprise, "
                   "interested in API and SDKs, wants a demo.",
    }],
    output_format=ContactInfo,
)

contact = response.parsed_output      # a validated ContactInfo instance
print(contact.name)                   # "Jane Doe"
print(contact.interests)              # ["API", "SDKs"]
```

`response.parsed_output` is a real typed object. Your editor autocompletes it. mypy checks
it. There is no parsing step, no `try/except json`, no defensive `.get()`.

**This should be your default.** It's the shortest path and the safest one.

### The explicit form — raw schema

When you need a schema that isn't a Pydantic model — one loaded from a file, generated
dynamically, or shared with another service:

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    messages=[{"role": "user", "content": text}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "plan": {"type": "string"},
                    "demo_requested": {"type": "boolean"},
                },
                "required": ["name", "email", "plan", "demo_requested"],
                "additionalProperties": False,
            },
        }
    },
)

import json
text = next(b.text for b in response.content if b.type == "text")
data = json.loads(text)      # guaranteed to parse and match the schema
```

Two details that are easy to get wrong:

- It's `output_config={"format": {...}}`. An older top-level `output_format` parameter on
  `messages.create()` is deprecated — if you've seen it in a tutorial, that tutorial is stale.
- `"additionalProperties": False` and an explicit `"required"` list are **required** for
  strict schema enforcement. Omit them and the guarantee weakens.

---

## 8.5 · Level 4 — strict tool use

The other route to the same guarantee, through the tool-calling surface.

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16_000,
    messages=[{"role": "user", "content": "Book a flight to Tokyo for 2 on March 15"}],
    tools=[{
        "name": "book_flight",
        "description": "Book a flight to a destination",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "date": {"type": "string", "format": "date"},
                "passengers": {"type": "integer", "enum": [1, 2, 3, 4, 5, 6, 7, 8]},
            },
            "required": ["destination", "date", "passengers"],
            "additionalProperties": False,
        },
    }],
)
```

With `strict: True`, the `tool_use.input` is guaranteed to validate against your schema.

Note the placement: **`strict` is a top-level field on the tool definition**, alongside `name`
and `description` — not on `tool_choice`. Getting this wrong is a common error.

### Which surface to use

| Use `output_config.format` | Use strict tools |
|---|---|
| The model is **returning a value** | The model is **requesting an action** |
| Extraction, classification, analysis | Search, calculate, send, book |
| One shape, always | Several possible actions, model chooses |
| No side effects | Side effects happen after |

If you're extracting data, use structured output. If you're building an agent, use tools —
that's Part IV. They compose: you can use both in one request, with tools for actions and a
schema for the final answer.

> **One incompatibility to know:** schema-constrained output cannot be combined with document
> citations — that combination returns a 400. If you need cited answers with structure,
> Chapter 15 covers the patterns.

---

## 8.6 · Schema design

This is the part that isn't in the documentation, and it's what separates a schema that works
from one that fights you. **The schema is part of your prompt.** The model reads the field
names, the descriptions, and the types, and they shape its behaviour as much as your
instructions do.

### 1 · Field names are instructions

```python
# ❌ The model must guess what these mean
class Result(BaseModel):
    val: str
    n: int
    flag: bool

# ✅ The names carry the specification
class Result(BaseModel):
    customer_full_name: str
    total_line_items: int
    requires_manual_review: bool
```

Descriptive names measurably improve extraction accuracy. They cost a few tokens and pay for
themselves immediately.

### 2 · Use descriptions for anything non-obvious

```python
from pydantic import BaseModel, Field


class Invoice(BaseModel):
    invoice_number: str = Field(
        description="The invoice identifier, usually labelled 'Invoice #' or 'Ref'."
    )
    total_amount: float = Field(
        description="Final amount due after tax and discounts, in the invoice's currency. "
                    "Not the subtotal."
    )
    currency: str = Field(
        description="ISO 4217 code, e.g. USD, EUR, INR. Infer from the currency symbol."
    )
```

That `total_amount` description — *"not the subtotal"* — is worth more than a paragraph of
prompt. Descriptions go into the schema, the schema goes to the model, and disambiguation
lands exactly where the ambiguity is.

### 3 · Enums instead of free strings

```python
# ❌ You'll get "high", "High", "HIGH", "urgent", "P1", "very high"...
class Ticket(BaseModel):
    priority: str

# ✅ Only four values are representable
from typing import Literal

class Ticket(BaseModel):
    priority: Literal["P0", "P1", "P2", "P3"]
```

With schema constraints, the model *cannot* emit anything else. No normalisation code, no
surprise categories appearing in your dashboard six months later.

### 4 · Put reasoning fields first — and understand why

This is the most valuable technique in the chapter.

Generation is sequential. The model produces the JSON token by token, in order. **A field
earlier in the schema is generated before a later one — and therefore becomes context for
it.**

So you can get chain-of-thought *inside* a structured output:

```python
class Classification(BaseModel):
    reasoning: str = Field(
        description="Brief analysis of the ticket: what is broken, who is affected, "
                    "and whether a workaround exists."
    )
    priority: Literal["P0", "P1", "P2", "P3"]
    requires_escalation: bool
```

The model must write its reasoning before committing to a priority, and the priority is then
generated with that reasoning in context. Same mechanism as section 7.6, but structured and
parseable.

**Reverse the order and you lose it.** `priority` first means the model commits to an answer
and then rationalises it — which is both less accurate and less useful, because the
"reasoning" is now a post-hoc justification rather than an input to the decision.

You also get a free debugging log: when a classification looks wrong, `reasoning` tells you
what the model thought it was looking at.

### 5 · Make absence representable

If a field might legitimately not exist, say so in the type. Otherwise the model must invent
something, because the schema demands a value.

```python
class Extraction(BaseModel):
    name: str
    email: str | None = Field(
        default=None,
        description="Email address if explicitly present. null if the text contains none. "
                    "Do not guess or construct an address."
    )
```

**This is hallucination prevention at the schema level.** A required `email: str` on a
document with no email forces fabrication — the model has no legal way to express "there
isn't one." Making it optional gives it one.

### 6 · Flat beats deeply nested

```python
# ❌ Four levels deep — more places to go wrong, harder to validate partially
class Response(BaseModel):
    result: ResultWrapper      # .data.items[0].attributes.value

# ✅ Flatter — easier for the model, easier for you
class Response(BaseModel):
    items: list[Item]
    total_count: int
```

Deep nesting increases error rates and makes partial extraction impossible. Flatten unless the
nesting carries real meaning.

### 7 · Don't ask for self-assessed confidence

```python
# ❌ A number-shaped guess
class Result(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
```

From section 5.10: the model doesn't compute calibrated uncertainty. A `confidence` field
produces a plausible-looking float that correlates weakly, if at all, with correctness — and
it's dangerous precisely because it *looks* like a signal you can threshold on.

Prefer something the model can actually observe about its own input:

```python
class Result(BaseModel):
    answer: str
    found_in_source: bool = Field(
        description="True only if the answer appears explicitly in the provided document."
    )
    supporting_quote: str | None = Field(
        description="The exact sentence from the document supporting this answer, "
                    "or null if the answer is not directly stated."
    )
```

`supporting_quote` is verifiable — **you can check whether that string actually occurs in the
source document.** That's a real signal. A confidence score is not.

---

## 8.7 · When it still goes wrong

Schema constraints guarantee the output *parses and matches the shape*. They guarantee
nothing about whether it's **correct**.

Four failure modes survive, and you need a plan for each:

**1 · Well-formed and wrong.** The schema is satisfied; the extracted email belongs to the
wrong person. Only evals catch this (Chapter 22).

**2 · Fabricated to satisfy a required field.** Covered above — make absence representable.

**3 · Truncation.** If generation hits `max_tokens` mid-object, you get invalid JSON despite
the constraint. **Always check `stop_reason`:**

```python
if response.stop_reason == "max_tokens":
    raise ValueError("output truncated — raise max_tokens")
```

**4 · Refusal.** The model may decline. `stop_reason == "refusal"` means there's no JSON to
parse, and retrying identically won't help.

### A repair loop, used sparingly

When you're on a surface without schema constraints, feed the validation error back:

```python
async def extract_with_repair(text: str, attempts: int = 2) -> Contact:
    messages = [{"role": "user", "content": build_prompt(text)}]

    for attempt in range(attempts):
        raw = await call_model(messages)
        try:
            return Contact.model_validate_json(raw)
        except ValidationError as e:
            if attempt == attempts - 1:
                raise
            logger.warning("repair attempt %d: %s", attempt + 1, e.errors())
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    f"That did not validate:\n{e.json()}\n\n"
                    f"Return corrected JSON matching the schema. Output only the JSON."},
            ]

    raise RuntimeError("unreachable")
```

> **Cap this at two attempts, and log every repair.** A repair loop doubles latency and cost,
> and a rising repair rate is a *signal* — it means your schema or prompt needs fixing, not
> that you need a third retry. Treat repairs as a metric, not a solution.

---

## 8.8 · Practical typing patterns

```python
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)


class Invoice(BaseModel):
    # Reasoning first — see 8.6.4
    document_analysis: str = Field(
        description="What kind of document this is and where the key figures appear."
    )

    # Constrained categories
    document_type: Literal["invoice", "receipt", "purchase_order", "other"]

    # Required core fields
    invoice_number: str
    issue_date: date

    # Optional, with explicit guidance about absence
    due_date: date | None = Field(
        default=None, description="Payment due date. null if not stated."
    )

    # Nested, but only one level
    line_items: list[LineItem] = Field(
        default_factory=list,
        description="Every billable line. Empty list if none are itemised.",
    )

    # Verifiable grounding, not self-assessed confidence
    total_amount: float
    total_source_text: str = Field(
        description="The exact text from the document where the total appears."
    )
```

Notes on the choices: `date` gets parsed and validated for you, so `"March 15th"` either
becomes a real date or raises. `Field(ge=...)` enforces ranges. `default_factory=list` avoids
the mutable-default trap from section 2.10. And `total_source_text` is checkable against the
original.

### Lists of things

A common need — extracting many items — has a common trap:

```python
# ❌ The top level of a schema must be an object, not an array
output_format = list[Contact]

# ✅ Wrap it
class ContactList(BaseModel):
    contacts: list[Contact]
    total_found: int = Field(description="Number of distinct contacts identified.")
```

That `total_found` field is not redundant. Asking the model to state a count makes omissions
more visible — if it says 5 and returns 3, something went wrong and you can detect it in code.

---

## 8.9 · Build it

**A document extraction pipeline.** Extend your Chapter 3 project:

```
src/genai_toolkit/extraction/
├── schemas.py       Pydantic models for each document type
├── extractor.py     the extraction calls, with retry and repair
├── validation.py    post-extraction checks (does the quote actually appear?)
└── pipeline.py      concurrent extraction over many documents
```

Requirements:

1. **Three document types** — invoice, support ticket, meeting notes — each with a properly
   designed schema following all seven principles from section 8.6.
2. **Schema-constrained output** via `messages.parse()`. No manual JSON parsing anywhere.
3. **Grounding validation** — for every field with a `*_source_text`, verify the quoted string
   actually appears in the source. Flag it when it doesn't. **This catches real
   hallucinations, in code, with no model involved.**
4. **Concurrent processing** with a `Semaphore`, and partial failure handling — one bad
   document must not lose the batch.
5. **A metrics record** per run: success rate, repair rate, grounding-failure rate, cost,
   latency.
6. **Tested against a fake client** — every failure path, no API calls in CI.
7. `make check` green.

### Then break it

1. Feed a document with **no** email into a schema where `email: str` is required. Watch it
   fabricate one. Then make it optional and watch it return `null`. **This is the most
   instructive five minutes in the chapter.**
2. Set `max_tokens` low enough to truncate a large extraction. Confirm your `stop_reason`
   check fires before the parse does.
3. Move the `reasoning` field from first to last. Re-run 20 documents. Measure the accuracy
   difference.
4. Give it a document of a completely different type. Does it force a bad fit, or does your
   `document_type: Literal[...]` enum let it say "other"?
5. Feed it a scanned-PDF-to-text mess with broken line breaks. This is what real input looks
   like, and it's how you find out your schema was designed for clean data.

---

## 8.10 · Exercises

**1 · Ladder the reliability.** Implement the same extraction at all four levels. Run each
over 100 documents. Record the parse-failure rate for each. **Plot it.** You'll never argue
about this again.

**2 · Reasoning-field ablation.** Build a classifier with `reasoning` first, then move it
last, then remove it. Measure accuracy for all three over the same 50 inputs.

**3 · Make fabrication impossible.** Take a schema with three required fields. Find documents
missing each one. Redesign so the model can express absence. Verify it does.

**4 · Grounding checker.** Write `verify_grounding(extraction, source) -> list[str]` returning
the names of fields whose `*_source_text` does not appear in the source. Run it over a batch
and report the rate.

**5 · Enum migration.** Take a free-text `category: str` field with 200 real extracted values.
Cluster them by hand. Design a `Literal` enum covering 95%, plus `"other"`. Re-run and measure
what lands in `"other"`.

**6 · Repair-loop economics.** Implement the repair loop. Measure the added latency and cost
of each repair attempt. Compute: at what failure rate does a repair loop cost more than simply
using schema constraints? *(The answer will be "always," and that's the point.)*

**7 · Schema as prompt.** Take one schema and improve only the **field descriptions** —
change nothing else. Measure extraction accuracy before and after. Document the delta in your
prompt changelog from Chapter 7.

**8 · Handle the list trap.** Build an extractor for a document containing an unknown number
of items. Include `total_found`. Find a case where the count disagrees with the list length,
and decide what your code should do about it.

---

## 8.11 · Checkpoint

> **Move on to Chapter 9 when all of these are true.**

**Explain, out loud:**

1. The difference between validating output and constraining generation — and why the second
   is categorically stronger.
2. Why a `reasoning` field must come *first* in the schema, in terms of how generation works.
3. Why a required `email: str` on a document with no email causes hallucination.
4. Why `supporting_quote` is a real signal and `confidence: float` is not.
5. What schema constraints guarantee, and the four failure modes they don't.
6. When to use `output_config.format` versus strict tool use.

**Write from memory:**

7. A Pydantic schema following all seven design principles.
8. A `messages.parse()` call returning a validated instance.
9. A raw `output_config` schema with `additionalProperties: False` and `required`.
10. A grounding check that verifies a quoted string appears in the source.

**Verify:**

11. Your pipeline extracts from three document types with zero manual JSON parsing.
12. Your grounding checker has caught at least one real fabrication.
13. You have measured the reasoning-field-position effect yourself.
14. Tests cover every failure path against a fake client, with no network calls.

---

## 8.12 · Going deeper (optional)

**Read the JSON Schema specification** — at least the sections on `required`,
`additionalProperties`, `enum`, and `format`. You'll write schemas for years; two hours here
pays off permanently.

**Read Pydantic's validators documentation.** `field_validator` and `model_validator` let you
express constraints a JSON Schema can't — "due date must be after issue date," "line items
must sum to the total." That last one is a genuine hallucination detector you can run in code.

**If you want to understand the mechanism:** search for "constrained decoding" and "grammar-
based sampling." Knowing that the constraint works by masking invalid tokens at each
generation step — rather than by validating afterwards — makes the guarantee feel real rather
than magical.

---

<div align="center">

**[← Chapter 7](../ch07-prompting-as-engineering/)** · **[The Book](../../readme.md)** · **[Chapter 9 → Context, Cost & Latency](../ch09-context-cost-latency/)**

*Chapter 8 of 31 · Week 8*

</div>
