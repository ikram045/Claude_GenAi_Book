# Chapter 11 · Document Processing & Chunking

### The unglamorous layer where most RAG systems are actually won or lost

> **Week 11, part 1 · ~11 hours · Heavy code, messy data**
>
> Nobody puts chunking in a conference talk. It is, nonetheless, the layer where more RAG
> systems fail than any other — because every downstream stage inherits its mistakes and
> none of them can repair one.

---

## 11.0 · Why this chapter exists

A retrieval system can only return a chunk. If the answer to a question spans a boundary
between two chunks, **no amount of clever search will find it.** Your embedding model can be
excellent, your reranker state of the art, your prompt beautifully written — and the answer
is simply not retrievable, because you cut it in half at index time.

Here is what that looks like in practice:

```
Original document:
    "Enterprise customers receive a 30-day refund window.
     Standard customers receive 14 days."

Chunked badly (fixed 60 characters):
    Chunk 1: "Enterprise customers receive a 30-day refund window. Stand"
    Chunk 2: "ard customers receive 14 days."

Query: "How long do standard customers have to request a refund?"
Retrieved: Chunk 2 — "ard customers receive 14 days."
```

Fourteen days *what*? Fourteen days from when? Which customers — the chunk starts mid-word. A
language model handed that fragment will either say it doesn't know, or worse, guess.

This chapter is about not doing that. It's the least glamorous work in Part III and the
highest-leverage, because **chunking errors are unfixable downstream.**

---

## 11.1 · The pipeline

Four stages, each with its own failure modes:

```
  raw file            ┌──────────────┐
  (.pdf .docx .html)  │  EXTRACTION  │  → get the text out, keep the structure
                      └──────────────┘
                             │
                      ┌──────────────┐
                      │   CLEANING   │  → remove noise, normalise, deduplicate
                      └──────────────┘
                             │
                      ┌──────────────┐
                      │   CHUNKING   │  → split into retrievable units
                      └──────────────┘
                             │
                      ┌──────────────┐
                      │  ENRICHMENT  │  → metadata, context, summaries
                      └──────────────┘
                             │
                          chunks → embeddings (Chapter 10) → index (Chapter 12)
```

Most tutorials cover stage three and skip the other three. Stages one and four are where the
quality actually comes from.

---

## 11.2 · Extraction: the messy reality

> **A PDF is a presentation format, not a data format.** It describes where to draw glyphs on
> a page. It does not, in general, know what a paragraph is, what order the text should be
> read in, or which cells belong to which table row.

This is the single most important thing to understand before you write a document pipeline,
because it sets your expectations correctly: extraction is **lossy and hard**, and no library
solves it completely.

### What goes wrong, by format

| Format | Typical problems |
|---|---|
| **PDF** | Multi-column text interleaved into nonsense; tables flattened into word soup; headers and footers repeated on every page; ligatures (`ﬁ` → `fi`); hyphenated line breaks; scanned pages with no text layer at all |
| **HTML** | Navigation, cookie banners, ads and footers extracted as content; `<div>` soup with no semantic structure; JavaScript-rendered content invisible to a fetcher |
| **DOCX** | Tracked changes; comments; text boxes in arbitrary order; footnotes interleaved |
| **Slides** | Speaker notes mixed with slide content; no reading order; text in images |
| **Code** | Comments and code need different treatment; imports at the top matter to every function below |
| **Email** | Quoted reply chains duplicating content; signatures; disclaimers longer than the message |
| **Spreadsheets** | Meaning lives in a 2D layout that linearises terribly |

### The rules that actually help

**1 · Prefer the structured source.** If the PDF was generated from Markdown, index the
Markdown. If the HTML page has an API behind it, use the API. Every conversion loses
information, and the best extraction is the one you don't have to do.

**2 · Extract to Markdown, not plain text.** Markdown preserves headings, lists, tables and
emphasis in a form that both your chunker and the language model understand. Plain text throws
away structure you'll wish you had.

**3 · Look at the output. Actually look at it.** Not the counts — the text. Open twenty
extracted documents and read them. You will find repeated page footers, a table rendered as
`Name Age City Ada 36 London Grace 45 NYC`, and a two-column paper read across the columns
instead of down them. **You cannot find these problems in aggregate statistics.**

**4 · Detect scanned pages.** A PDF page with no text layer extracts to an empty string, and a
pipeline that doesn't check will silently index nothing. Count characters per page; flag
anything near zero for OCR or human attention.

**5 · Keep the provenance.** Every chunk must be traceable to its source file, page and
position. Citation in Chapter 15 depends on it, and debugging depends on it far sooner.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ExtractedDocument:
    text: str                       # markdown
    source_path: str
    page_map: list[tuple[int, int]] # (char_offset, page_number)
    metadata: dict                  # title, author, dates, anything the format gave you
    extraction_warnings: list[str]  # empty pages, OCR needed, table failures
```

That `extraction_warnings` field is not decorative. It's what lets you report *"we indexed
1,200 documents; 43 had pages with no extractable text"* instead of silently losing 43
documents' worth of content.

---

## 11.3 · Cleaning

Between extraction and chunking, remove what isn't content. Each of these is cheap and each
measurably improves retrieval:

| Problem | Fix |
|---|---|
| Repeated headers/footers | Detect lines appearing on most pages; strip them |
| Hyphenated line breaks | Join `inter-\nnational` → `international` |
| Excessive whitespace | Collapse 3+ newlines to 2; strip trailing spaces |
| Boilerplate | Legal disclaimers, nav menus, "click here to unsubscribe" |
| Duplicate documents | Hash the content; index once |
| Near-duplicates | Different versions of the same policy — decide which wins |

> **Be conservative.** An over-aggressive cleaner that strips a line looking like a header but
> actually containing a definition has destroyed information that no downstream stage can
> recover. When in doubt, keep it — and log what you removed so you can audit the decision.

Near-duplicates deserve particular attention. If your corpus contains the 2023 and 2025
versions of the same policy, retrieval will return whichever happens to score higher, and
that's how the wrong parental-leave number reaches a user. That was Chapter 1's opening bug,
and it starts here.

---

## 11.4 · The chunking tradeoff

The chunk is two things at once, and they pull in opposite directions:

- **The unit of retrieval.** Precision wants small chunks — one idea each, so a match is
  unambiguous.
- **The unit of context.** Comprehension wants large chunks — enough surrounding material for
  the answer to make sense.

```
   TOO SMALL                                          TOO LARGE
   ├──────────────────────────────────────────────────────────┤
   "fourteen days"                    a whole 4,000-word chapter

   ✓ precise match                    ✓ complete context
   ✗ no context — meaningless         ✗ diluted vector (section 10.5)
   ✗ answer split across chunks       ✗ wastes context window
   ✗ more chunks = more storage       ✗ buries the answer in noise
```

There is no universal right answer. There is a right answer *for your corpus and your
queries*, and **you find it by measuring** — which is Chapter 14, and which is why this chapter
ends by telling you to come back.

A reasonable starting point, to be tuned rather than trusted: **400–800 tokens per chunk, with
10–20% overlap.**

---

## 11.5 · Strategies, worst to best

### 1 · Fixed-size character splitting

```python
chunks = [text[i : i + 1000] for i in range(0, len(text), 1000)]
```

Splits mid-word, mid-sentence, mid-table. The only thing to be said for it is that it's two
lines. **Never ship this.** It appears in this book solely so you recognise it in other
people's code.

### 2 · Fixed-size word or token splitting

Your Chapter 2 chunker. Respects word boundaries, ignores everything else. Acceptable as a
baseline to measure against.

### 3 · Sentence-aware splitting

Split into sentences, then group sentences until you reach the target size. Never breaks
mid-sentence. A real improvement, and a sensible fallback.

Use a proper sentence splitter, not `text.split(".")` — abbreviations, decimals, ellipses and
quotations will defeat the naive version immediately.

### 4 · Recursive character splitting

Try to split on the most meaningful separator available, and fall back progressively:

```python
SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]

def recursive_split(text: str, max_size: int, seps: list[str]) -> list[str]:
    """Split on the largest separator that produces pieces under max_size."""
    if len(text) <= max_size:
        return [text]

    for i, sep in enumerate(seps):
        if sep and sep in text:
            parts = text.split(sep)
            out, current = [], ""
            for part in parts:
                candidate = current + sep + part if current else part
                if len(candidate) <= max_size:
                    current = candidate
                else:
                    if current:
                        out.append(current)
                    # the part itself may still be too big — recurse with the next separator
                    if len(part) > max_size:
                        out.extend(recursive_split(part, max_size, seps[i + 1 :]))
                        current = ""
                    else:
                        current = part
            if current:
                out.append(current)
            return out

    return [text[i : i + max_size] for i in range(0, len(text), max_size)]
```

This is the sensible general-purpose default. It prefers section breaks, falls back to
paragraphs, then lines, then sentences, then words — degrading gracefully rather than
catastrophically.

### 5 · Structural chunking — the one you should usually use

If your documents have structure, **use it**. Headings exist precisely because a human decided
where one topic ends and another begins. That's exactly the judgment you're trying to make.

```python
@dataclass(frozen=True)
class Section:
    heading_path: list[str]      # ["Refund Policy", "Enterprise Customers"]
    content: str
    level: int
```

Split on headings, then recursively split any section that's still too large — keeping the
heading path on every resulting piece.

**Why heading paths matter so much:** they solve the "fourteen days *what*?" problem for free.

```
Chunk text:  "Standard customers receive 14 days."
Heading path: Billing → Refunds → Time Limits
```

Now the chunk is self-describing, its embedding is about refunds rather than about the number
fourteen, and a citation can tell the user exactly where it came from. One piece of metadata,
three problems solved.

Apply the same logic to code (split on function and class boundaries, keep the file path and
imports), and to conversations (split on turns, never mid-message).

### 6 · Semantic chunking

Embed each sentence, and start a new chunk wherever consecutive sentences become dissimilar —
letting topic shifts determine boundaries.

Conceptually appealing. In practice: expensive (an embedding per sentence at index time),
slow, and **frequently no better than good structural chunking.** Worth trying only when your
documents genuinely lack structure — transcripts, OCR output, unformatted notes — and worth
measuring before you commit.

### 7 · Late chunking

A newer idea worth knowing. Embed the *whole document* first with a long-context embedding
model, then derive chunk vectors from the relevant spans of that full-document representation.

Each chunk's vector is informed by the entire document, so a chunk saying "it costs $40"
carries the context of what "it" is. Requires a model that supports it, and it's promising
rather than universal — but it addresses the core tension of section 11.4 directly, which is
why it's interesting.

---

## 11.6 · Overlap

Let adjacent chunks share some text, so a boundary can't destroy an idea.

```
    Chunk 1:  [════════════════════]
    Chunk 2:            [════════════════════]
    Chunk 3:                      [════════════════════]
                        └───┬───┘
                         overlap
```

**What it buys:** an answer that straddles a boundary appears complete in at least one chunk.
Context carries across. Coreference ("it", "this policy") sometimes survives.

**What it costs:** storage and embedding cost scale with the duplication — 20% overlap means
20% more chunks. Near-duplicate chunks compete for the same top-k slots, which can crowd out
genuinely different material.

**A sane default: 10–20% of chunk size.** With structural chunking, you often need *less*
overlap, because your boundaries are already in sensible places. That's another argument for
using structure: it makes overlap cheaper.

> **Overlap is a patch for bad boundaries.** The better your boundaries, the less you need.
> Reach for better boundaries first.

---

## 11.7 · Metadata

Half of a good retrieval system, and routinely treated as an afterthought.

```python
@dataclass(frozen=True)
class Chunk:
    # content
    text: str

    # provenance — enables citation and debugging
    document_id: str
    source_path: str
    page_number: int | None
    char_start: int
    char_end: int
    chunk_index: int

    # structure — enables context and filtering
    heading_path: tuple[str, ...]
    section_level: int

    # document-level — enables filtering (Chapter 12) and recency logic
    document_title: str
    document_type: str
    created_at: date | None
    updated_at: date | None
    author: str | None
    version: str | None

    # derived — enables hybrid search and reranking
    token_count: int
    content_hash: str
```

Every field earns its place:

- **`char_start` / `char_end`** let you prove a chunk against its source, expand a retrieved
  chunk to its neighbours, and cite exactly.
- **`heading_path`** gives self-describing chunks and human-readable citations.
- **`updated_at` / `version`** are how you prefer the current policy over the 2023 one — the
  Chapter 1 bug, solved with a filter.
- **`document_type`** lets a query about invoices skip the marketing corpus entirely.
- **`content_hash`** deduplicates and enables the embedding cache from section 10.8.

> **Metadata you didn't capture at index time cannot be recovered later without re-indexing.**
> It is much cheaper to capture a field you might not use than to re-process a million
> documents because you wish you had. Be generous here.

---

## 11.8 · Contextual enrichment

The single highest-value technique in this chapter, and one most tutorials don't mention.

### The problem

```
Chunk:  "The limit was raised to 500 concurrent connections in this release."
```

Which product? Which release? Raised from what? Embedded as-is, this chunk is about "limits"
and "connections" in the abstract. A query naming the actual product may never find it.

### The fix

Before embedding, prepend a short statement of where the chunk sits:

```
Context: From "Acme Gateway v4.2 Release Notes" (March 2026), section
"Performance Improvements". The previous limit was 100.

Chunk: The limit was raised to 500 concurrent connections in this release.
```

Now the embedding carries the product, the version, the date and the section. A query about
"Acme Gateway connection limits" finds it easily.

### Two ways to generate it

**Cheap and deterministic — do this always.** Build the context from metadata you already have:

```python
def contextualise(chunk: Chunk) -> str:
    parts = [f'From "{chunk.document_title}"']
    if chunk.created_at:
        parts.append(f"({chunk.created_at:%B %Y})")
    if chunk.heading_path:
        parts.append(f"section \"{' → '.join(chunk.heading_path)}\"")
    return f"Context: {' '.join(parts)}.\n\n{chunk.text}"
```

Free, instant, and it captures most of the benefit.

**Expensive and better — for high-value corpora.** Ask a language model to write a one-or-two
sentence situating description for each chunk, given the whole document:

```python
ENRICH_PROMPT = """<document>
{document}
</document>

<chunk>
{chunk}
</chunk>

Write 1–2 sentences situating this chunk within the document, so it can be
understood in isolation. Resolve any pronouns or references that point outside
the chunk. Output only those sentences."""
```

This measurably improves retrieval — published results show meaningful reductions in retrieval
failure rates. It is also a language-model call **per chunk**, which on a large corpus is
expensive.

**Two things make it affordable**, and both are things you already know:

1. **Prompt caching.** The document is the stable prefix and the chunk is the variable suffix.
   Every chunk after the first in a document hits the cache at ~10% of input price (section
   9.4). This is close to the perfect caching workload.
2. **Batch pricing.** Indexing is the definitive latency-insensitive job — roughly half price
   again (section 9.6).

> **Store the enriched text for embedding, and the original text for display.** The context
> prefix helps retrieval; showing it to the user is noise, and feeding it to the answering
> model wastes tokens. Two fields: `embedding_text` and `display_text`.

---

## 11.9 · The awkward cases

### Tables

Tables break everything. A table flattened to prose loses the row/column relationship that
*was* the information.

Options, in order of preference:

1. **Keep it as Markdown.** Models read Markdown tables well, and the structure survives.
2. **Never split a table across chunks.** A table without its header row is useless. If it's
   too big, repeat the header in each piece.
3. **For large tables, generate a description** with a language model and index that alongside
   the table — the description is far more findable than the raw grid.
4. **For genuinely tabular questions, don't use RAG.** "What was Q3 revenue in the EMEA
   region?" is a database query. Give the model a SQL tool instead (Part IV).

### Code

- Split on function and class boundaries, never mid-function.
- Keep imports and the file path with every chunk — they're context for everything below.
- Index the docstring and the implementation together; people search in prose and need the
  code.
- Keep a symbol path in metadata: `src/auth/session.py → SessionManager.refresh`.

### Lists and procedures

A numbered procedure split at step 4 produces two chunks that are each wrong. Keep procedures
whole where possible; if you must split, repeat the procedure's title and note "steps 1–5 of
12" in the chunk.

### Conversations

Split on turn boundaries, never mid-message. Include enough preceding turns for the exchange
to make sense. Attribute every turn to a speaker — "we'll refund it" means something different
depending on who said it.

---

## 11.10 · Build it

**A real document processing pipeline.** This becomes the ingestion layer of Project C, and it
extends Project A.

```
src/genai_toolkit/ingestion/
├── extractors/
│   ├── base.py        Extractor Protocol
│   ├── markdown.py
│   ├── html.py
│   ├── pdf.py
│   └── code.py
├── cleaning.py        headers/footers, hyphenation, whitespace, boilerplate
├── chunkers/
│   ├── base.py        Chunker Protocol
│   ├── fixed.py       baseline, for measurement
│   ├── recursive.py
│   └── structural.py  ← the default
├── enrichment.py      metadata context + optional LLM context
├── dedupe.py          exact and near-duplicate detection
└── pipeline.py        orchestration, concurrency, resumability
```

Requirements:

1. **Four formats** — Markdown, HTML, PDF, source code — behind one `Extractor` Protocol.
2. **Extraction warnings** surfaced, not swallowed: empty pages, failed tables, encoding
   problems.
3. **Three chunkers** behind one Protocol, switchable by config, so Chapter 14 can compare
   them.
4. **Structural chunking with heading paths** as the default.
5. **Complete metadata** — every field in section 11.7, with exact character offsets.
6. **Contextual enrichment**, metadata-based always and LLM-based optionally, with prompt
   caching enabled and a cost report.
7. **Deduplication** by content hash, with near-duplicate detection reported.
8. **An offset-fidelity test**: slicing the source by `char_start:char_end` reproduces the
   chunk exactly. *(This is a property test, not an example test — reviewers notice.)*
9. `make check` green.

### Then look at the output

**This is the exercise.** Not the code — the inspection.

1. Process 20 real documents. **Read 50 chunks by hand.** Yes, really. Note every one that is
   confusing in isolation.
2. For each confusing chunk, work out which stage caused it: extraction, cleaning, or
   boundary choice.
3. Fix the top three causes. Re-run. Read 50 more.

Nobody does this, and it is the reason so many RAG systems are mediocre. **The chunks are the
product.** If a human can't understand a chunk in isolation, no model will.

### Break it deliberately

1. Run the fixed-size chunker on a document with tables and headings. Read the output. Feel
   the difference.
2. Set chunk size to 50 tokens, then to 4,000. Search the same query against both. Observe
   both failure modes from section 11.4.
3. Set overlap to 0. Find a fact that straddles a boundary and becomes unfindable.
4. Disable contextual enrichment. Search for something using a term that appears only in the
   document title. Watch it fail, then re-enable and watch it work. **This is the most
   convincing experiment in the chapter.**
5. Feed it a scanned PDF with no text layer. Does your pipeline warn, or silently index
   nothing?
6. Feed it the same document twice. Does deduplication catch it?

---

## 11.11 · Exercises

**1 · Extraction bake-off.** Take 10 real PDFs and extract them with three different libraries.
Compare the output **by reading it**. Score each on: reading order, table fidelity,
header/footer noise. Pick one, and write down why.

**2 · The header/footer detector.** Write a function that finds lines appearing on more than
60% of pages and strips them. Test it against a document where a repeated line is genuinely
content — and make sure you don't destroy it.

**3 · Chunk size sweep.** Chunk the same corpus at 200, 400, 800, 1,600 and 3,200 tokens. Run
20 queries against each. Record which size answers the most questions correctly. **Plot it.**
*(This is Chapter 14 arriving early, and it's the right way to choose a chunk size.)*

**4 · Boundary damage audit.** Take 100 chunks. For each, judge: is this comprehensible in
isolation? Compute the percentage. Change one thing about your chunker and recompute. This
number is a real quality metric and you can track it over time.

**5 · Contextual enrichment ROI.** Enrich a corpus with LLM-generated context. Measure: cost
with and without prompt caching, index time, and retrieval quality on 30 queries. **Compute
the cost per point of improvement**, then decide whether you'd pay it.

**6 · Table torture test.** Find a document with a complex table. Try four approaches: flatten
to text, keep as Markdown, LLM-generated description, description plus table. Query it five
ways. Which wins?

**7 · Code chunker.** Write one that splits a Python file on function and class boundaries,
preserves imports in every chunk, and records a symbol path. Test it on a real file with nested
classes and decorators.

**8 · Offset fidelity as a property test.** Generate random documents and random chunker
settings. Assert that for every chunk, `source[chunk.char_start:chunk.char_end] ==
chunk.text`. Run 1,000 cases. *(If you looked up `hypothesis` in Chapter 3, use it here.)*

---

## 11.12 · Checkpoint

> **Move on to Chapter 12 when all of these are true.**

**Explain, out loud:**

1. Why chunking errors cannot be fixed by better search.
2. Why a PDF is a presentation format, and what that means for your pipeline.
3. The two opposing pressures that make chunk size a tradeoff.
4. Why structural chunking usually beats every alternative.
5. What a heading path solves, and why it's worth carrying on every chunk.
6. Why contextual enrichment works, and the two techniques that make it affordable.
7. Why overlap is a patch for bad boundaries rather than a good in itself.

**Write from memory:**

8. A recursive splitter with a separator fallback chain.
9. A `Chunk` dataclass with complete provenance and structural metadata.
10. A metadata-based contextualiser.
11. The offset-fidelity assertion.

**Verify:**

12. Your pipeline handles four formats and surfaces extraction warnings.
13. You have read 50 of your own chunks by hand and fixed the top three problems.
14. You have demonstrated the contextual-enrichment experiment (break it, then fix it).
15. Your chunk-size sweep has a plot and a chosen value you can defend.

Number 13 is the one that separates people who build good retrieval from people who build
demos. **Read your chunks.**

---

## 11.13 · Going deeper (optional)

**Read about contextual retrieval.** Anthropic published results on prepending
LLM-generated context to chunks before embedding, with measured reductions in retrieval
failure. It's the empirical backing for section 11.8, and it shows what a properly measured
retrieval claim looks like.

**Look into document layout analysis.** Models that understand a page's visual structure —
columns, tables, figures — before extracting text. This is where PDF extraction is heading,
and it's substantially better than text-layer scraping on hard documents.

**If your corpus has no structure:** read about semantic chunking implementations and
topic-segmentation algorithms. Measure before adopting — the theory is more attractive than
the typical result.

**If you want to see the state of the art:** search for "late chunking" and long-context
embedding models. It's the most interesting recent attempt to dissolve the section 11.4
tradeoff rather than manage it.

---

<div align="center">

**[← Chapter 10](../ch10-embeddings-deeply/)** · **[The Book](../../readme.md)** · **[Chapter 12 → Vector Databases](../ch12-vector-databases/)**

*Chapter 11 of 31 · Week 11*

</div>
