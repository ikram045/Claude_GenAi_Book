# Chapter 2 · Python for Dart Developers

### You already know how to program. This is a translation, not an education.

> **Week 1 · ~14 hours · Heavy code**
>
> This is the longest chapter in Part I, and the one you'll come back to most. Treat it as
> a reference you read once end-to-end and then raid for the next six months.

---

## 2.0 · Why this chapter exists

Every Python tutorial you will find is written for someone who has never programmed. They
spend three chapters on what a variable is. You would lose a week to material you learned
years ago, and — worse — you'd learn Python as a *first* language rather than as a
*second*, which means nobody would ever tell you the things that actually trip up an
experienced developer coming from a typed, compiled, null-safe language.

Those things are specific, and there are about fifteen of them:

- Python's type hints look like Dart's type annotations but do **nothing** at runtime.
- Calling an `async` function in Python does **not** start it. In Dart it does.
- `if my_list:` is valid and idiomatic. In Dart that's a compile error.
- Default arguments are evaluated **once**, at function definition — which creates the
  single most infamous bug in the language.
- Python programmers deliberately let exceptions fly where you'd check first.
- There's no `new`, no `final`, no sound null safety, no `private` keyword.

This chapter is those fifteen things, plus everything else you need, in the order that
makes them stick. You will not be a Python expert at the end of it. You will be someone who
can read and write Python professionally, which is all this job requires.

---

## 2.1 · Why Python, honestly

It's worth knowing why you're learning this particular language, because the answer is not
"it's the best language" and pretending otherwise makes the rough edges feel like personal
failures rather than history.

Python won AI for reasons that are almost entirely **accidents of history**:

**It got there first.** In the 2000s, scientists needed something better than MATLAB for
numerical work. `NumPy` appeared in 2006 and was good enough. Once NumPy existed, every
numerical library built on it. Once every numerical library was Python, every ML framework
was Python. Once every ML framework was Python, every ML researcher learned Python. Once
every ML researcher knew Python, every new model shipped with Python bindings.

That's it. That's the whole story. It's a thirty-year compounding accident.

**It's a good glue language.** Python is genuinely slow — often 50–100× slower than Dart
for raw computation. This matters far less than you'd expect, because in this field Python
is almost never doing the computation. It's orchestrating: calling a C++ library, calling a
CUDA kernel, calling an HTTP API. Python is the remote control, not the engine.

**It's readable enough that scientists tolerate it.** Not a small thing. The field's
practitioners are often domain experts first and programmers second.

### What you'll like

Fast to write. Extraordinary ecosystem — for any task in this book, a mature library
exists. The REPL makes experimentation genuinely pleasant. Type hints plus Pydantic gets
you surprisingly close to the safety you're used to.

### What will annoy you

No sound null safety, so `None` can appear where you didn't expect it. Type hints that lie
to you. Slow. Packaging was a disaster for twenty years (Chapter 3 fixes this with modern
tooling — it's genuinely solved now). No real multithreading in the default build.

> **The right attitude:** Python is a tool you're learning because it's where the work is,
> not because it's beautiful. You'll come to like it more than you expect. You will also
> miss Dart's type system every single week, and you should — that instinct will make you a
> better Python programmer than most Python programmers, because you'll reach for Pydantic
> where they reach for a raw dict.

---

## 2.2 · The first shock: whitespace is syntax

Before anything else, the thing that will feel wrong for about two days.

```dart
// Dart — braces define blocks. Indentation is decoration.
void greet(String name) {
  if (name.isNotEmpty) {
    print("Hello, $name");
  }
}
```

```python
# Python — indentation IS the block. The colon opens it.
def greet(name):
    if name:
        print(f"Hello, {name}")
```

No braces. No semicolons. A colon opens a block, and **indentation closes it**. Four spaces
per level, by universal convention — never tabs, never two spaces.

This is not cosmetic. Get the indentation wrong and you change the program's meaning:

```python
def process(items):
    results = []
    for item in items:
        results.append(item * 2)
        return results          # ← inside the loop: returns after ONE item
```

```python
def process(items):
    results = []
    for item in items:
        results.append(item * 2)
    return results              # ← outside the loop: returns all of them
```

In Dart, a misplaced brace is usually a compile error. In Python, misplaced indentation is
usually a *working program that does the wrong thing*. This is the single most common
source of confusion in your first week.

**The fix is not discipline — it's tooling.** Configure your editor now: show whitespace,
four-space indent, and let the formatter (Chapter 3) handle it. After a week you'll stop
noticing, and within a month you'll find braces noisy. Everyone does.

---

## 2.3 · The translation table

Print this. Pin it near your monitor for two weeks.

| Concept | Dart | Python |
|---|---|---|
| Declare a variable | `var x = 5;` / `int x = 5;` | `x = 5` / `x: int = 5` |
| Constant | `final x = 5;` / `const x = 5;` | `X = 5` *(convention only — not enforced)* |
| String interpolation | `"Hi $name"` | `f"Hi {name}"` |
| Null / absence | `null` | `None` |
| Nullable type | `String?` | `str \| None` *(or `Optional[str]`)* |
| Null-safe access | `user?.name` | `user.name if user else None` |
| Null coalescing | `x ?? "default"` | `x if x is not None else "default"` |
| Function | `int add(int a, int b) => a + b;` | `def add(a: int, b: int) -> int: return a + b` |
| Anonymous function | `(x) => x * 2` | `lambda x: x * 2` |
| List | `List<int> xs = [1, 2];` | `xs: list[int] = [1, 2]` |
| Map / dict | `Map<String, int> m = {};` | `m: dict[str, int] = {}` |
| Set | `Set<int> s = {1, 2};` | `s: set[int] = {1, 2}` |
| Transform a list | `xs.map((x) => x * 2).toList()` | `[x * 2 for x in xs]` |
| Filter a list | `xs.where((x) => x > 2).toList()` | `[x for x in xs if x > 2]` |
| Create an object | `var p = Person("Ada");` | `p = Person("Ada")` *(no `new`)* |
| Class method | `void greet() { ... }` | `def greet(self): ...` |
| Private member | `_name` *(library-private, enforced)* | `_name` *(convention only)* |
| Async function | `Future<int> f() async { ... }` | `async def f() -> int: ...` |
| Await | `await f()` | `await f()` |
| Stream | `Stream<int>` | `AsyncIterator[int]` |
| Consume a stream | `await for (var x in s)` | `async for x in s:` |
| Run in parallel | `await Future.wait([a, b])` | `await asyncio.gather(a(), b())` |
| Exception | `throw Exception("x")` | `raise Exception("x")` |
| Catch | `try { } catch (e) { }` | `try: ... except Exception as e: ...` |
| Finally | `finally { }` | `finally:` |
| Import | `import 'x.dart';` | `import x` / `from x import y` |
| Entry point | `void main() { }` | `if __name__ == "__main__":` |
| Comment | `// x` , `/* x */` | `# x` , `"""x"""` |
| Equality | `a == b` *(value)* | `a == b` *(value)* |
| Identity | `identical(a, b)` | `a is b` |
| Length | `xs.length` | `len(xs)` |
| String → int | `int.parse("5")` | `int("5")` |
| Package manager | `pub` | `uv` *(see Chapter 3)* |

---

## 2.4 · Names are labels, not boxes

This looks like a triviality and is the root cause of three separate bugs later in the
chapter, so it's worth thirty seconds.

In Dart, a variable is roughly a **box** with a type, and you put values in it. In Python,
a variable is a **label you stick on an object**. The object exists independently; the name
just points at it.

```python
a = [1, 2, 3]
b = a               # b is a SECOND LABEL on the SAME list
b.append(4)
print(a)            # [1, 2, 3, 4]  ← a changed, because there is only one list
```

Dart does this too for objects, so it shouldn't shock you. What's different is that Python
does it *uniformly*, for everything, and there is no `final` to protect you:

```python
a = [1, 2, 3]
b = a.copy()        # now a genuinely separate list
b.append(4)
print(a)            # [1, 2, 3]
```

Two consequences to file away:

**1. Assignment never copies.** `b = a` is always "add another label," never "duplicate."
To copy, you must say so: `a.copy()`, `list(a)`, `a[:]`, or `copy.deepcopy(a)` for nested
structures.

**2. There is no `final`.** `CONSTANT_NAMES` in upper case are a promise between
programmers, not a guarantee from the language. Anyone can reassign them. This will feel
unsafe. It is unsafe. Everyone lives with it.

```python
MAX_TOKENS = 4096
MAX_TOKENS = 10     # Perfectly legal. No warning. Good luck.
```

---

## 2.5 · Types: hints, not guarantees

This is the biggest culture shock coming from Dart, and misunderstanding it costs people
real debugging hours.

Python's type annotations look reassuringly like Dart's:

```python
def greet(name: str, times: int = 1) -> str:
    return f"Hello, {name}! " * times
```

**They do absolutely nothing at runtime.**

```python
greet(42, "banana")
# Runs. No error at call time.
# Fails later, deep inside, with a confusing message — or worse, silently does
# something strange.
```

The interpreter reads annotations, stores them in `__annotations__`, and ignores them
completely. They exist for **humans and for static analysis tools**. Nothing enforces them
unless you run a type checker, which you will (Chapter 3: `mypy` / `pyright`).

### Why this design?

Python was dynamically typed for 25 years before type hints arrived in 2015. Making them
enforced would have broken essentially all existing code. So they're optional, gradual, and
external — a bolt-on that turned out to work far better than anyone expected.

### The rule for this book

> **Annotate everything.** Every function parameter, every return type, every class
> attribute. Then run a type checker in CI so the annotations can't drift into lies.

Most Python developers are sloppy about this. Coming from Dart, you won't be, and it will
make your code noticeably better than the median. It also matters more in AI work than
almost anywhere else, because you are constantly handling loosely-shaped data that came
back from a model, and untyped dictionaries flowing through a codebase is how you end up
with a `KeyError` in production at 2am.

### The type syntax you'll actually use

```python
from typing import Any, Callable, Literal

# Basics
name: str = "Ada"
age: int = 36
score: float = 0.92
active: bool = True

# Collections — lowercase built-ins, Python 3.9+
names: list[str] = ["Ada", "Grace"]
scores: dict[str, float] = {"ada": 0.9}
tags: set[str] = {"ai", "python"}
point: tuple[int, int] = (3, 4)            # fixed length, fixed types
row: tuple[str, ...] = ("a", "b", "c")     # any length, all str

# Nullable — Dart's String? becomes:
nickname: str | None = None                # Python 3.10+, preferred
# from typing import Optional
# nickname: Optional[str] = None           # older style, same meaning

# Union of several types
value: int | str | None = 5

# Functions as values — Dart's int Function(String)
parser: Callable[[str], int] = int

# A fixed set of allowed values — closest thing to a Dart enum in a signature
Model = Literal["opus", "sonnet", "haiku"]
def call(model: Model) -> str: ...

# The escape hatch. Means "I give up on typing this."
payload: Any = {"anything": "goes"}
```

> **`Any` is contagious.** Once a value is `Any`, every expression derived from it is
> unchecked, and the checker goes quiet exactly where you most need it. Use it when
> interfacing with genuinely untyped data, and convert to a real type — a Pydantic model —
> as early as you can. In LLM work, that boundary is usually "the moment the model's
> response arrives."

### `None` is not `null`

Close, but the ergonomics are different, and the difference bites:

```dart
// Dart — the compiler forces you to handle it
String? name = getName();
print(name.length);        // COMPILE ERROR. Won't build.
print(name?.length);       // fine
print(name!.length);       // your promise, your crash
```

```python
# Python — nothing stops you
name: str | None = get_name()
print(len(name))           # Runs happily until name is None, then:
                           # TypeError: object of type 'NoneType' has no len()
```

There is no `?.` operator and no `!`. You check manually:

```python
if name is not None:
    print(len(name))

# Common idiom, relies on None being falsy:
if name:
    print(len(name))
# Careful: this is also False for "" — usually what you want, occasionally not.

# Null-coalescing equivalents:
display = name or "Anonymous"                       # falls back on "" too
display = name if name is not None else "Anonymous" # strict about None only
```

**Always compare to `None` with `is`, never `==`.** `is` tests identity, and there is
exactly one `None` object in a running program. `==` can be overridden by a class and give
you a surprising answer.

---

## 2.6 · Strings, numbers, and the truth

### Strings

```python
s = "double"            # identical to 'single' — pick one and be consistent
multi = """Spans
multiple lines."""      # also how docstrings are written

name, n = "Ada", 3
f"Hello {name}"                  # f-string — the only interpolation you should use
f"{n * 2}"                       # any expression works
f"{0.9184:.2%}"                  # '91.84%'  — format specs
f"{1234567:,}"                   # '1,234,567'
f"{name=}"                       # "name='Ada'"  — debugging gift, prints name and value
```

That last one, `f"{name=}"`, will save you a thousand `print` statements. Remember it.

Useful operations, many of which have no direct Dart equivalent:

```python
s = "  Hello, World  "
s.strip()                   # 'Hello, World'
s.lower()                   # '  hello, world  '
s.replace("World", "Ada")
s.split(",")                # ['  Hello', ' World  ']
", ".join(["a", "b"])       # 'a, b'   ← note: separator.join(items)
s.startswith("  He")        # True
"World" in s                # True  ← `in` works on strings, lists, dicts, sets

text = "Hello, World"
text[0]                     # 'H'
text[-1]                    # 'd'    ← negative indexing. Dart has nothing like this.
text[0:5]                   # 'Hello'
text[7:]                    # 'World'
text[:5]                    # 'Hello'
text[::-1]                  # 'dlroW ,olleH'  ← reversed
```

**Slicing is one of Python's genuinely great features** and it works on every sequence —
strings, lists, tuples. `xs[a:b:c]` means "from `a`, up to but not including `b`, stepping
by `c`." You'll use it constantly, especially for chunking documents in Part III.

### Numbers

```python
7 / 2          # 3.5   ← always float. Dart gives 3.5 too, but Dart's ~/ is /
7 // 2         # 3     ← floor division
7 % 2          # 1
2 ** 10        # 1024  ← exponent. Dart needs pow()
int(3.9)       # 3     ← truncates toward zero
round(3.5)     # 4
```

Python integers have **unlimited precision** — no overflow, ever:

```python
2 ** 1000      # a 302-digit number, exactly correct
```

Floats are ordinary IEEE-754 and misbehave in the ordinary way (`0.1 + 0.2 != 0.3`). For
money, use `decimal.Decimal`. You'll meet this in Chapter 9 when tracking token costs.

### Truthiness

In Dart, `if` demands a `bool`. Python accepts anything, and applies these rules:

**Falsy:** `False`, `None`, `0`, `0.0`, `""`, `[]`, `{}`, `()`, `set()`
**Truthy:** everything else

```python
items = []
if items:                  # False — empty list is falsy
    print("has items")

if not items:
    print("empty")         # ← this runs. Idiomatic Python.
```

This is idiomatic and you should adopt it. But there is one trap, and it's a real one:

```python
count = 0
if count:                  # False! Even though count is a perfectly valid value
    print("we have a count")

# When zero is meaningful, be explicit:
if count is not None:
    print("we have a count")
```

This bites hardest with function arguments that legitimately accept `0` or `""`. When the
distinction between "absent" and "empty" matters, always test `is None`.

---

## 2.7 · Collections

Four built-in types. You'll use `list` and `dict` constantly, `set` often, `tuple`
regularly.

### `list` — like Dart's `List`

```python
xs: list[int] = [1, 2, 3]

xs.append(4)               # [1, 2, 3, 4]      — Dart: xs.add(4)
xs.extend([5, 6])          # [1, 2, 3, 4, 5, 6]— Dart: xs.addAll(...)
xs.insert(0, 0)            # [0, 1, 2, ...]
xs.remove(3)               # removes the first 3 by VALUE
popped = xs.pop()          # removes and returns the last
popped = xs.pop(0)         # removes and returns index 0
len(xs)                    # Dart: xs.length
xs.sort()                  # in place, returns None  ← note!
ys = sorted(xs)            # returns a new sorted list
xs.reverse()               # in place
3 in xs                    # membership test
xs.index(3)                # first position of value 3
xs.count(3)                # how many 3s
```

> **A trap worth marking:** `xs.sort()` sorts in place and returns `None`. So
> `ys = xs.sort()` gives you `None`, not a sorted list. Use `sorted(xs)` when you want a
> new list. The same pattern applies to `reverse()`, `append()`, and most mutating methods:
> **if it mutates, it returns `None`.** This is a deliberate design rule.

Sorting with a key — the equivalent of Dart's `compareTo`:

```python
people = [{"name": "Ada", "age": 36}, {"name": "Grace", "age": 45}]
sorted(people, key=lambda p: p["age"])                 # ascending
sorted(people, key=lambda p: p["age"], reverse=True)   # descending
sorted(words, key=len)                                 # by length
```

### `dict` — like Dart's `Map`

```python
scores: dict[str, float] = {"ada": 0.9, "grace": 0.95}

scores["ada"]                    # 0.9
scores["nobody"]                 # KeyError! ← Dart returns null. Python raises.
scores.get("nobody")             # None — safe
scores.get("nobody", 0.0)        # 0.0  — safe with a default

scores["turing"] = 0.99          # insert or update
del scores["turing"]             # delete
"ada" in scores                  # membership tests KEYS
scores.keys() / .values() / .items()

for name, score in scores.items():        # the idiomatic iteration
    print(f"{name}: {score}")

scores.setdefault("new", 0.0)             # get, inserting a default if absent
merged = {**a, **b}                       # merge — b wins on conflicts
merged = a | b                            # same, Python 3.9+
```

**The `KeyError` difference matters.** Dart's `map["missing"]` quietly returns `null`, and
you find out later. Python raises immediately, at the line where you asked. This is
genuinely better — errors should surface where they happen — but it means you must use
`.get()` anywhere absence is legitimate. This pattern is everywhere in LLM work, because
API responses often omit optional fields.

Dictionaries preserve insertion order (guaranteed since Python 3.7), which is often quietly
useful.

### `set` — unordered, unique

```python
tags: set[str] = {"ai", "python", "ai"}   # {'ai', 'python'} — dupes vanish

tags.add("rag")
tags.discard("ai")                 # no error if absent
"python" in tags                   # O(1) — the reason sets exist

a, b = {1, 2, 3}, {2, 3, 4}
a & b          # {2, 3}      intersection
a | b          # {1,2,3,4}   union
a - b          # {1}         difference
a ^ b          # {1, 4}      symmetric difference
```

Reach for a set whenever you're about to write `if x not in my_list` inside a loop. A list
membership test is O(n); a set's is O(1). On 10,000 items that's the difference between
instant and noticeable, and it shows up constantly when deduplicating retrieved chunks.

`set()` is the empty set — **`{}` is an empty dict**, which catches everyone once.

### `tuple` — immutable, fixed

```python
point: tuple[int, int] = (3, 4)
point[0]                    # 3
point[0] = 5                # TypeError — immutable

x, y = point                # unpacking
a, b = b, a                 # swap, no temp variable

def min_max(xs): return min(xs), max(xs)   # returning multiple values
low, high = min_max([3, 1, 4])
```

Dart has records now (`(int, int)`), so this should feel familiar. Two things tuples give
you that lists don't: they can be dictionary keys (lists can't, being mutable), and they
signal intent — "this is a fixed structure, not a collection."

---

## 2.8 · Comprehensions

If there is one piece of syntax that makes Python code look like Python, it's this. Coming
from Dart's `.map().where().toList()` chains, it's the same idea with the parts reordered.

```dart
// Dart
final doubled = xs.map((x) => x * 2).toList();
final evens   = xs.where((x) => x % 2 == 0).toList();
final both    = xs.where((x) => x % 2 == 0).map((x) => x * 2).toList();
```

```python
# Python
doubled = [x * 2 for x in xs]
evens   = [x for x in xs if x % 2 == 0]
both    = [x * 2 for x in xs if x % 2 == 0]
```

Read it as: **`[ what-I-want  for  each-item  in  source  if  condition ]`**

The shape carries to the other collection types:

```python
{x: x ** 2 for x in range(5)}          # dict comprehension
{w.lower() for w in words}             # set comprehension
(x * 2 for x in xs)                    # GENERATOR — lazy, not a list. See 2.14.
```

Nested loops read outer-to-inner, exactly like the `for` statements they replace:

```python
pairs = [(x, y) for x in [1, 2] for y in "ab"]
# [(1,'a'), (1,'b'), (2,'a'), (2,'b')]

flat = [item for row in matrix for item in row]        # flattening
```

A realistic one you'll write in Part III:

```python
chunks = [
    {"text": c.text, "score": c.score}
    for c in results
    if c.score > 0.7
]
```

> **When to stop.** Comprehensions are for *transforming*, not for *doing*. If yours has
> two conditions and a nested loop and you have to read it twice, write a `for` loop. A
> clear loop beats a clever comprehension every time, and this is the most common way
> intermediate Python programmers make their code worse.
>
> Never use a comprehension purely for side effects:
> ```python
> [print(x) for x in xs]        # builds a useless list of None. Don't.
> for x in xs: print(x)         # say what you mean
> ```

---

## 2.9 · Control flow

Mostly unsurprising. The differences are in `for` and in two newer constructs.

```python
if score > 0.9:
    grade = "A"
elif score > 0.8:            # not "else if"
    grade = "B"
else:
    grade = "C"

grade = "A" if score > 0.9 else "B"     # ternary, reads left-to-right oddly at first
```

### `for` is `for-in`, always

There is no C-style `for (int i = 0; ...)`. Python's `for` always iterates a sequence.

```python
for item in items: ...
for i in range(5): ...              # 0,1,2,3,4
for i in range(2, 10, 2): ...       # 2,4,6,8

for i, item in enumerate(items): ...            # index AND item
for i, item in enumerate(items, start=1): ...   # 1-based

for name, score in zip(names, scores): ...      # parallel iteration
```

`enumerate` and `zip` are the two you'll use daily. Writing `for i in range(len(items))` is
the clearest possible signal that someone is writing Python with a C accent — use
`enumerate`.

### `for`/`else` — genuinely unusual

```python
for chunk in chunks:
    if chunk.matches(query):
        print("found it")
        break
else:
    print("no match in any chunk")     # runs only if the loop never broke
```

Rare, but it appears in real code and is confusing the first time. Read `else` here as
"if we got through the whole loop without breaking."

### `match` — pattern matching (3.10+)

Closer to Dart 3's `switch` expressions than to C's `switch`:

```python
match response:
    case {"type": "text", "text": str(content)}:
        print(content)
    case {"type": "tool_use", "name": name, "input": args}:
        run_tool(name, args)
    case {"type": "error", "code": 429}:
        back_off()
    case _:
        raise ValueError(f"unknown response type: {response}")
```

This destructures *and* matches at once. It's genuinely useful for handling the shaped
responses you'll get from model APIs in Part II.

### The walrus `:=` — assign inside an expression

```python
if (n := len(items)) > 10:
    print(f"too many: {n}")          # n is available here

while (line := f.readline()):
    process(line)
```

Use sparingly, but it's clean when you need a value both for a test and inside the block.

---

## 2.10 · Functions

Python's function parameters are more flexible than Dart's, and the flexibility is worth
learning properly because every library you use exploits it.

```python
def add(a: int, b: int) -> int:
    """Add two numbers.

    The first string in a function is its docstring. Tooling reads it,
    `help(add)` prints it. Write them for anything non-obvious.
    """
    return a + b
```

### Arguments: positional, keyword, defaults

```python
def search(query: str, limit: int = 10, rerank: bool = False) -> list[str]:
    ...

search("cats")                              # defaults used
search("cats", 5)                           # positional
search("cats", limit=5)                     # keyword — clearer, prefer this
search(query="cats", rerank=True)           # all keyword
search(limit=5, query="cats")               # order doesn't matter for keywords
```

Unlike Dart, **every parameter can be passed either positionally or by name** — no `{}`
needed to make it named. You can force the issue when you want to:

```python
def f(a, b, /, c, *, d):
    ...
# a, b : positional ONLY  (before the /)
# c    : either
# d    : keyword ONLY     (after the *)
```

Keyword-only parameters after `*` are excellent API design for booleans — it stops
`search("cats", True, False)` from ever being written.

### `*args` and `**kwargs`

```python
def log(*args, **kwargs):
    print(args)      # tuple of extra positional arguments
    print(kwargs)    # dict of extra keyword arguments

log(1, 2, three=3)   # (1, 2)  /  {'three': 3}
```

And in the other direction, for *unpacking*:

```python
nums = [1, 2, 3]
print(*nums)                      # same as print(1, 2, 3)

config = {"limit": 5, "rerank": True}
search("cats", **config)          # same as search("cats", limit=5, rerank=True)
```

You'll see `**kwargs` everywhere in ML libraries as a pass-through mechanism. It's flexible
and it destroys type safety, so use it sparingly in your own code.

### ⚠️ The mutable default argument

The most famous bug in Python. It will get you once. Let it be now, in a chapter, rather
than later, in production.

```python
def add_item(item: str, basket: list[str] = []) -> list[str]:
    basket.append(item)
    return basket

add_item("apple")     # ['apple']
add_item("banana")    # ['apple', 'banana']   ← !!!
add_item("cherry")    # ['apple', 'banana', 'cherry']
```

**Why:** default values are evaluated **once**, when the `def` statement runs — not on each
call. So there is exactly one list, created at import time, shared by every call forever.

**The fix**, and it is always this fix:

```python
def add_item(item: str, basket: list[str] | None = None) -> list[str]:
    if basket is None:
        basket = []
    basket.append(item)
    return basket
```

> **Rule: never use a mutable value (`[]`, `{}`, `set()`, or an object) as a default.**
> Use `None` and build it inside. Linters (Chapter 3) catch this automatically — one more
> reason to have them on from day one.

### Functions are objects

```python
def double(x): return x * 2

f = double                  # no call — just a reference
f(5)                        # 10

list(map(double, [1, 2]))   # passing functions around
sorted(people, key=lambda p: p.age)

def make_multiplier(n):     # closures work as you'd expect
    def multiply(x):
        return x * n
    return multiply

triple = make_multiplier(3)
triple(5)                   # 15
```

`lambda` is limited to a single expression — no statements, no multi-line bodies. It exists
for short callbacks. Anything bigger gets a real `def`.

### ⚠️ Late-binding closures

The second classic trap, and it catches people who've just learned closures work:

```python
fs = [lambda: i for i in range(3)]
[f() for f in fs]            # [2, 2, 2]  ← not [0, 1, 2]
```

The closure captures the **variable** `i`, not its value at creation time. By the time you
call them, the loop is over and `i` is `2`. Fix by binding at definition:

```python
fs = [lambda i=i: i for i in range(3)]
[f() for f in fs]            # [0, 1, 2]
```

---

## 2.11 · Classes

```dart
// Dart
class Person {
  final String name;
  int age;

  Person(this.name, this.age);

  String greet() => "Hi, I'm $name";

  @override
  String toString() => "Person($name, $age)";
}

var p = Person("Ada", 36);
```

```python
# Python
class Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def greet(self) -> str:
        return f"Hi, I'm {self.name}"

    def __repr__(self) -> str:
        return f"Person({self.name!r}, {self.age})"

p = Person("Ada", 36)        # no `new`
```

Four differences to absorb:

**1. No `new`.** Call the class like a function.

**2. `self` is explicit** and is always the first parameter of an instance method. Python
does not inject it invisibly. Forgetting it produces a confusing argument-count error, and
you will forget it about six times.

**3. `__init__` is the constructor** — one per class. No named constructors like Dart's
`Person.fromJson()`. The equivalent is a `@classmethod`:

```python
class Person:
    @classmethod
    def from_json(cls, data: dict) -> "Person":
        return cls(data["name"], data["age"])

p = Person.from_json({"name": "Ada", "age": 36})
```

**4. Privacy is a convention.** `_name` means "internal, don't touch" and is enforced by
nothing but professional courtesy. `__name` (two underscores) triggers name mangling, which
is mild obfuscation, not privacy. Coming from Dart's library-private `_`, this feels
alarming. It's fine in practice — people respect the underscore.

### Dunder methods

Double-underscore methods hook into language syntax. The equivalents of Dart's `toString`,
`operator ==`, `hashCode`:

```python
class Vector:
    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y

    def __repr__(self) -> str:            # what you see in the REPL / debugger
        return f"Vector({self.x}, {self.y})"

    def __str__(self) -> str:             # what print() shows
        return f"({self.x}, {self.y})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)

    def __hash__(self) -> int:            # needed if you want it in a set/dict
        return hash((self.x, self.y))

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y)

    def __len__(self) -> int: ...         # enables len(obj)
    def __getitem__(self, i): ...         # enables obj[i]
    def __iter__(self): ...               # enables for x in obj
    def __contains__(self, x): ...        # enables x in obj
```

**Always write `__repr__`.** It's what the debugger and REPL show you, and the default
(`<__main__.Vector object at 0x7f3a...>`) tells you nothing. Five minutes of writing
`__repr__` saves hours of debugging.

### Properties — Dart's getters and setters

```python
class Document:
    def __init__(self, text: str) -> None:
        self._text = text

    @property
    def word_count(self) -> int:          # accessed as doc.word_count, no parens
        return len(self._text.split())

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if not value.strip():
            raise ValueError("text cannot be empty")
        self._text = value
```

### Inheritance and duck typing

```python
class Retriever:
    def search(self, query: str) -> list[str]:
        raise NotImplementedError

class VectorRetriever(Retriever):
    def search(self, query: str) -> list[str]:
        return ["result"]

    def __init__(self, index) -> None:
        super().__init__()
        self.index = index
```

Python has no `interface` or `implements`. It has **duck typing**: if an object has a
`.search()` method, it can be used wherever a searcher is expected, related by inheritance
or not. For type checking, use `Protocol` — structural typing, checked statically:

```python
from typing import Protocol

class Searchable(Protocol):
    def search(self, query: str) -> list[str]: ...

def run(s: Searchable, q: str) -> list[str]:
    return s.search(q)          # any object with a matching search() satisfies this
```

`Protocol` is the closest thing to Dart's implicit interfaces, and it's the right tool when
you want swappable components — which, in Part III, you will, constantly.

---

## 2.12 · `dataclass` and Pydantic

You will rarely write a plain class in this field. You'll write data containers, and there
are two good tools for that.

### `@dataclass` — the `freezed` equivalent, built in

```python
from dataclasses import dataclass, field

@dataclass
class Chunk:
    text: str
    source: str
    score: float = 0.0
    tags: list[str] = field(default_factory=list)    # ← mutable default, done right

c = Chunk(text="hello", source="doc.pdf")
print(c)             # Chunk(text='hello', source='doc.pdf', score=0.0, tags=[])
c == Chunk(...)      # value equality, free
```

You get `__init__`, `__repr__` and `__eq__` generated for you. Note `default_factory` —
that's the sanctioned way to give a mutable default, and it calls the factory once per
instance.

Immutability, the closest thing to Dart's `final` fields:

```python
@dataclass(frozen=True)
class Config:
    model: str
    max_tokens: int = 1024

c = Config("opus")
c.model = "sonnet"       # FrozenInstanceError — actually enforced
```

`frozen=True` also makes instances hashable, so they work as dict keys and in sets.

### Pydantic — the one that matters here

`dataclass` gives you structure. **Pydantic gives you validation at runtime**, and that is
the whole game when you're handling data that came from outside your program — a model
response, a JSON API, a config file.

```python
from pydantic import BaseModel, Field

class SearchResult(BaseModel):
    text: str
    source: str
    score: float = Field(ge=0.0, le=1.0)       # must be between 0 and 1
    tags: list[str] = []

# Validates AND coerces on construction
r = SearchResult(text="hi", source="a.pdf", score="0.9")
r.score          # 0.9 — the string was coerced to float

SearchResult(text="hi", source="a.pdf", score=1.5)
# ValidationError: score — Input should be less than or equal to 1
```

This is the answer to your Dart instincts. Type hints do nothing at runtime — but Pydantic
reads those same hints and **enforces them**, at the boundary, where data enters your
system.

```python
# Parsing untrusted JSON — the everyday use
raw = '{"text": "hi", "source": "a.pdf", "score": 0.9}'
result = SearchResult.model_validate_json(raw)      # typed, validated, or it raises

result.model_dump()          # → dict
result.model_dump_json()     # → JSON string
```

> **This is why Chapter 8 is called "Structured Output."** When you ask a model for JSON,
> you get back a *string that you hope is JSON*. Pydantic is the wall between that hope and
> the rest of your program. Learn it well — it is, without exaggeration, the most-used
> non-AI library in professional LLM code.

**When to use which:** `dataclass` for internal structures you fully control; Pydantic the
moment data crosses a boundary — API request, API response, config file, model output.

---

## 2.13 · Errors, and the EAFP culture

Syntactically, this is familiar:

```python
try:
    result = risky()
except ValueError as e:
    print(f"bad value: {e}")
except (KeyError, IndexError) as e:      # multiple types
    print(f"lookup failed: {e}")
except Exception as e:                   # catch-all — use sparingly
    print(f"unexpected: {e}")
    raise                                # re-raise, preserving the traceback
else:
    print("no exception happened")       # runs only if try succeeded
finally:
    cleanup()                            # always runs
```

Custom exceptions are just classes:

```python
class RetrievalError(Exception):
    """Raised when the retrieval layer cannot answer."""

class IndexNotFound(RetrievalError):
    def __init__(self, name: str) -> None:
        super().__init__(f"index not found: {name}")
        self.name = name
```

Chaining preserves the original cause, which matters enormously when debugging layered
systems:

```python
try:
    connect()
except ConnectionError as e:
    raise RetrievalError("could not reach the vector store") from e
```

### The cultural difference: EAFP vs LBYL

This is the part that isn't syntax, and it's the part that makes Python code read
differently from Dart code.

**LBYL** — "Look Before You Leap." Check first, then act. Your instinct.

```python
if "score" in data and data["score"] is not None:
    value = float(data["score"])
else:
    value = 0.0
```

**EAFP** — "Easier to Ask Forgiveness than Permission." Just try it, handle the failure.
Python's preference.

```python
try:
    value = float(data["score"])
except (KeyError, TypeError, ValueError):
    value = 0.0
```

Why Python leans this way:

- **It's atomic.** Between the check and the action in LBYL, things can change — a file can
  be deleted, another thread can mutate a dict. EAFP has no such gap.
- **Exceptions are cheap in Python.** Unlike Dart and JVM languages, raising and catching
  is not expensive, so it's a reasonable control-flow tool.
- **It handles all failure modes at once.** The LBYL version above still crashes if
  `data["score"]` is `"banana"`. The EAFP version doesn't.

You don't have to love it, but you'll read a lot of code written this way, and adopting it
where it genuinely reads better will make your code look native.

---

## 2.14 · Iterators and generators

This section matters more than it looks, because **streaming LLM responses are built
entirely on it**.

### Generators

A function with `yield` instead of `return` is a generator. It produces values lazily, one
at a time, and remembers where it left off:

```python
def count_to(n: int):
    for i in range(n):
        yield i

for x in count_to(3):
    print(x)                # 0, 1, 2
```

The difference from returning a list is *memory and time*:

```python
def read_lines(path: str):
    with open(path) as f:
        for line in f:
            yield line.strip()      # one line in memory at a time

# Works on a 50GB file. A list-returning version would not.
for line in read_lines("huge.txt"):
    process(line)
```

Dart's closest equivalent is `sync*` / `yield`, so the concept should land quickly. The
generator expression is the lazy sibling of a list comprehension:

```python
squares = [x ** 2 for x in range(1_000_000)]     # builds a million-item list
squares = (x ** 2 for x in range(1_000_000))     # builds nothing until iterated

total = sum(x ** 2 for x in range(1_000_000))    # constant memory
```

> **Generators are single-use.** Once consumed, they're exhausted. Iterating a second time
> gives you nothing, silently. If you need the values twice, materialise with `list(...)`.
> This catches everyone at least once, usually while debugging something unrelated.

### `itertools`

A standard-library module of generator utilities. Three you'll actually use:

```python
from itertools import islice, chain, groupby

islice(gen, 10)                # first 10 items of a lazy sequence
chain(list_a, list_b)          # iterate several sequences as one
groupby(sorted_items, key=...) # group adjacent items (sort first!)
```

---

## 2.15 · Context managers — `with`

Dart's `try/finally` for cleanup has a dedicated, better-looking form in Python:

```python
with open("data.txt") as f:
    content = f.read()
# file is closed here — even if an exception was raised inside
```

You'll see `with` for files, database connections, locks, HTTP clients, and timers. Writing
your own is easy and worth knowing:

```python
from contextlib import contextmanager
import time

@contextmanager
def timed(label: str):
    start = time.perf_counter()
    try:
        yield                       # the body of the `with` block runs here
    finally:
        print(f"{label}: {time.perf_counter() - start:.2f}s")

with timed("embedding"):
    embed_documents(docs)
```

You'll write something very much like that in Chapter 9 for latency measurement.

---

## 2.16 · Async — the big one

You know async. You've written `Future`, `Stream`, `async`/`await` for years. About 80% of
this transfers directly. The remaining 20% contains one difference so important that
missing it will cost you an afternoon.

### The syntax you already know

```dart
// Dart
Future<String> fetch(String url) async {
  final response = await http.get(url);
  return response.body;
}
```

```python
# Python
import httpx

async def fetch(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

Nearly identical. Now the difference.

### ⚠️ Calling an async function does not start it

This is *the* thing.

```dart
// Dart — this STARTS running immediately.
// It executes synchronously until the first await, then returns a Future
// that is already in flight.
Future<String> f = fetch("https://example.com");
```

```python
# Python — this runs NOTHING.
# It creates a coroutine object and hands it to you, inert.
coro = fetch("https://example.com")     # nothing has happened
result = await coro                     # NOW it runs
```

A coroutine is a *description of work*, not work in progress. Nothing executes until you
`await` it or schedule it on the event loop.

The practical consequence, and the bug you'd otherwise write in week 3:

```python
# ❌ Looks concurrent. Is completely sequential.
async def get_all(urls):
    results = []
    for url in urls:
        results.append(await fetch(url))     # each await BLOCKS the next
    return results
# 10 urls × 200ms = 2000ms
```

```python
# ✅ Actually concurrent
import asyncio

async def get_all(urls):
    return await asyncio.gather(*(fetch(u) for u in urls))
# 10 urls ≈ 200ms
```

`asyncio.gather` is Dart's `Future.wait`. It takes coroutines, schedules them all, and
waits for all of them.

To start something *now* and await it later — Dart's default behaviour — you ask
explicitly:

```python
task = asyncio.create_task(fetch(url))    # starts running now
do_other_work()
result = await task                       # collect later
```

> **Internalise this:** in Dart, async functions are eager. In Python, they're lazy.
> `create_task` is how you buy eagerness. Almost every "why is my async code slow?" question
> from a newcomer has this as its answer.

### Getting into async

Dart's `main` can be `async`. Python needs an explicit entry point, because there's no
event loop running until you start one:

```python
async def main() -> None:
    result = await fetch("https://example.com")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())        # creates the loop, runs main, tears the loop down
```

You cannot `await` at the top level of a script. Everything async must be reachable from a
single `asyncio.run()`.

### Streams → async generators

Dart's `Stream<T>` maps to Python's async generator, and this is exactly the shape of a
streaming LLM response:

```dart
// Dart
Stream<String> tokens() async* {
  yield "Hello";
  yield " world";
}

await for (final t in tokens()) { print(t); }
```

```python
# Python
from collections.abc import AsyncIterator

async def tokens() -> AsyncIterator[str]:
    yield "Hello"
    yield " world"

async for t in tokens():
    print(t, end="", flush=True)
```

Here's a realistic version of what you'll write in Chapter 6 — worth reading now even
though the API details come later, because it shows how naturally the pieces fit:

```python
async def stream_answer(question: str) -> AsyncIterator[str]:
    """Yield the model's response token by token as it arrives."""
    async with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": question}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def main() -> None:
    async for chunk in stream_answer("Explain embeddings simply."):
        print(chunk, end="", flush=True)
```

If you've built a Flutter UI on a `StreamBuilder`, you have already built exactly this,
with different spelling.

### More useful async tools

```python
await asyncio.sleep(1.0)                        # never time.sleep() in async code

async with asyncio.timeout(5.0):                # 3.11+
    await slow_operation()

sem = asyncio.Semaphore(5)                      # limit concurrency — rate limits!
async def limited(url):
    async with sem:
        return await fetch(url)

results = await asyncio.gather(*tasks, return_exceptions=True)
# exceptions come back as values instead of cancelling the whole group
```

That `Semaphore` pattern is not optional trivia — it's how you stay inside an API provider's
rate limits while still running concurrently. You'll use it in Part III when embedding
thousands of chunks.

### About threads

Python's default build has a **Global Interpreter Lock**: only one thread executes Python
bytecode at a time. Threads therefore don't help with CPU-bound work the way Dart isolates
do. (Free-threaded builds are arriving, but assume the GIL for now.)

This matters less than it sounds for you, because LLM work is overwhelmingly I/O-bound —
waiting on network calls — and `asyncio` handles that perfectly. When you genuinely need
CPU parallelism, use `multiprocessing` (separate processes, closest to Dart isolates) or
push the work into a library whose heavy lifting happens in C.

---

## 2.17 · Modules, packages, imports

```python
import json                          # whole module
import numpy as np                   # with an alias
from pathlib import Path             # one name from a module
from typing import Any, Callable     # several
from .retrieval import search        # relative, within your own package
```

A **module** is a `.py` file. A **package** is a directory of modules. Modern Python doesn't
require `__init__.py`, but including one is still the clearer choice and controls what the
package exports.

```
myproject/
├── pyproject.toml
└── src/
    └── myproject/
        ├── __init__.py
        ├── retrieval.py
        └── models.py
```

Every module has a `__name__`. When run directly it's `"__main__"`; when imported it's the
module's name. Hence:

```python
def main() -> None:
    ...

if __name__ == "__main__":
    main()
```

This is Python's `void main()`, and the guard means the file can be *both* a script and an
importable module — the code only runs when executed directly, not when imported.

> **Never use `from module import *`.** It dumps unknown names into your namespace,
> shadows things silently, and makes it impossible to tell where anything came from. Every
> style guide bans it, and every codebase that ignored the ban regrets it.

Chapter 3 covers project layout, virtual environments and dependency management properly.
For now, know that `import` searches a path, and that path is controlled by your
environment — which is exactly why "it works on my machine" happens, and exactly what
Chapter 3 fixes.

---

## 2.18 · The standard library you'll actually use

Python's stdlib is enormous. This is the 5% that covers 95% of your work:

```python
from pathlib import Path        # file paths — ALWAYS use this, never string paths
import json                     # json.loads / json.dumps
import re                       # regular expressions
import os                       # os.environ for config and API keys
import sys                      # sys.argv, sys.exit
import asyncio                  # the event loop
import logging                  # logging, not print, in real code
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Protocol, Literal
from functools import lru_cache, wraps, partial
import itertools
```

Three worth a closer look:

```python
# pathlib — path handling that doesn't make you think about separators
p = Path("data") / "docs" / "report.pdf"    # the / operator joins paths
p.exists(); p.stem; p.suffix; p.parent
p.read_text(); p.write_text("hi")
list(Path("data").glob("**/*.pdf"))          # recursive search

# Counter — frequency counting, free
from collections import Counter
Counter(["a", "b", "a"]).most_common(1)      # [('a', 2)]

# defaultdict — no more "if key not in dict" dances
from collections import defaultdict
groups = defaultdict(list)
for chunk in chunks:
    groups[chunk.source].append(chunk)        # no initialisation needed

# lru_cache — memoisation in one line
from functools import lru_cache

@lru_cache(maxsize=1024)
def embed(text: str) -> list[float]:
    return expensive_api_call(text)           # identical inputs hit the cache
```

That `lru_cache` decorator will save you real money in Part III. Embedding the same text
twice is pure waste, and this is the cheapest possible fix.

---

## 2.19 · Idioms that mark you as fluent

Small things, but they're the difference between Python that reads naturally and Python
that reads like translated Dart.

```python
# Unpacking
a, b = b, a                      # swap
first, *rest = [1, 2, 3, 4]      # first=1, rest=[2,3,4]
*init, last = [1, 2, 3, 4]       # init=[1,2,3], last=4

# Chained comparison — no && needed
if 0 <= score <= 1:
    ...

# any() / all()
if any(c.score > 0.9 for c in chunks): ...
if all(c.text for c in chunks): ...

# Ternary and default-value idioms
name = user.name if user else "anonymous"
limit = config.get("limit") or 10        # careful: 0 falls through to 10

# enumerate and zip instead of index arithmetic
for i, item in enumerate(items, start=1): ...
for name, score in zip(names, scores): ...

# Underscore for values you don't need
for _ in range(3): ...
_, extension = filename.split(".")

# Readable numeric literals
MAX_TOKENS = 200_000

# Multi-line strings for prompts — you'll do this constantly
import textwrap
PROMPT = textwrap.dedent("""
    You are a helpful assistant.
    Answer using only the provided context.
""").strip()

# Debugging gift
print(f"{score=} {chunk.source=}")     # score=0.87 chunk.source='a.pdf'
```

---

## 2.20 · The gotcha checklist

Every trap in this chapter, in one place. Come back here when something behaves strangely.

| # | Gotcha | What happens | The fix |
|:---:|---|---|---|
| 1 | Mutable default argument | Default is shared across all calls, forever | Use `None`, build inside |
| 2 | `xs.sort()` returns `None` | `ys = xs.sort()` gives `None` | Use `sorted(xs)` |
| 3 | `{}` is a dict | `set()` is the empty set | Say `set()` |
| 4 | `0` and `""` are falsy | `if count:` skips a valid zero | `if count is not None:` |
| 5 | `is` vs `==` | `is` is identity; only correct for `None`/`True`/`False` | `==` for values, `is` for `None` |
| 6 | `dict[key]` raises | `KeyError`, unlike Dart's `null` | `.get(key, default)` |
| 7 | Generators are single-use | Second iteration yields nothing, silently | `list(gen)` if needed twice |
| 8 | Async call doesn't start | Sequential code that looks concurrent | `asyncio.gather` / `create_task` |
| 9 | Late-binding closures | All closures see the final loop value | `lambda i=i: ...` |
| 10 | Type hints don't enforce | Wrong types flow through silently | Run `mypy`; use Pydantic at boundaries |
| 11 | `b = a` doesn't copy | Mutating `b` mutates `a` | `a.copy()` / `copy.deepcopy(a)` |
| 12 | Shallow copy is shallow | Nested structures are still shared | `copy.deepcopy` |
| 13 | `time.sleep()` in async code | Blocks the entire event loop | `await asyncio.sleep()` |
| 14 | Indentation changes meaning | Working program, wrong behaviour | Formatter + visible whitespace |
| 15 | `import *` | Silent shadowing, unfindable names | Never do it |

---

## 2.21 · Build it

Type this out. Don't paste it. It exercises roughly two-thirds of the chapter in forty
lines, and every construct in it is one you'll use in Part II.

Create `code/chunker.py`:

```python
"""A tiny document chunker — the ancestor of what you'll build in Chapter 11."""

from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Iterator


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str
    index: int
    tags: tuple[str, ...] = field(default=())

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def __repr__(self) -> str:
        preview = self.text[:40].replace("\n", " ")
        return f"Chunk({self.source}#{self.index}, {self.word_count}w, {preview!r}...)"


def chunk_text(text: str, source: str, size: int = 50, overlap: int = 10) -> Iterator[Chunk]:
    """Split text into overlapping word windows.

    Overlap matters: a sentence split across a boundary is recoverable if the
    windows overlap, and lost forever if they don't. Chapter 11 goes deep on this.
    """
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")

    words = text.split()
    step = size - overlap

    for i, start in enumerate(range(0, len(words), step)):
        window = words[start : start + size]
        if not window:
            break
        yield Chunk(text=" ".join(window), source=source, index=i)


def main() -> None:
    sample = Path(__file__).parent / "sample.txt"
    if not sample.exists():
        sample.write_text(" ".join(f"word{i}" for i in range(200)))

    chunks = list(chunk_text(sample.read_text(), source=sample.name))

    print(f"{len(chunks)=}")
    for c in chunks[:3]:
        print(" ", c)

    total = sum(c.word_count for c in chunks)
    longest = max(chunks, key=lambda c: c.word_count)
    print(f"{total=} {longest.index=}")


if __name__ == "__main__":
    main()
```

Run it with `python code/chunker.py`.

**Now break it, deliberately.** Each of these teaches something specific:

1. Set `overlap=50, size=50`. Read the error. Why is that guard there?
2. Remove `frozen=True` and try `c.text = "x"`. Then put it back.
3. Change `chunk_text` to `return [...]` instead of yielding. What changes? What doesn't?
4. Iterate the generator twice *without* `list(...)` and watch the second loop do nothing.
5. Delete `__repr__` and print a chunk. Notice how much worse your debugging life just got.

---

## 2.22 · Exercises

In `exercises/`. Each has a test file; make them go green.

**1 · `dedupe.py`** — Write `dedupe(items: list[str]) -> list[str]` that removes duplicates
while **preserving order**. Use a set for the membership test, not a list. *(Tests
performance on 100,000 items — an O(n²) solution will time out.)*

**2 · `word_frequency.py`** — Given text, return the top `n` words as
`list[tuple[str, int]]`, case-insensitive, punctuation stripped, ignoring a stopword set.
Use `Counter`.

**3 · `safe_get.py`** — Write `safe_get(data: dict, path: str, default=None)` that walks a
dotted path (`"user.profile.name"`) through nested dicts and returns `default` if any step
is missing. Write it twice: once LBYL, once EAFP. Note which reads better.

**4 · `retry.py`** — Write an async `retry(fn, attempts=3, base_delay=0.1)` that retries a
failing coroutine with exponential backoff, re-raising if all attempts fail. *(You will use
this exact function in every project in this book.)*

**5 · `stream_words.py`** — Write an async generator that yields the words of a string one
at a time with a 50ms delay, and a consumer that prints them as they arrive. This is a
streaming LLM response with the model removed.

**6 · `parse_response.py`** — Define a Pydantic model for this shape:
```json
{"answer": "...", "confidence": 0.87, "sources": [{"doc": "a.pdf", "page": 3}]}
```
Validate that `confidence` is between 0 and 1 and `sources` is non-empty. Then feed it
three malformed inputs and handle the `ValidationError` gracefully. *(This is Chapter 8 in
miniature.)*

---

## 2.23 · Checkpoint

> **Move on to Chapter 3 when you can do all of these without looking anything up.**

**Write from memory:**

1. A `@dataclass` with a mutable field defaulted correctly.
2. A Pydantic model that validates a numeric range, plus the `try/except` around parsing
   untrusted JSON into it.
3. An async function that fetches 10 URLs **concurrently**, limited to 3 at a time.
4. An async generator that yields chunks, and the `async for` that consumes it.
5. A comprehension that filters and transforms in one expression.

**Explain out loud, in your own words:**

6. Why `def f(x, items=[])` is a bug, and precisely when the list is created.
7. What happens when you call an `async def` function in Python versus in Dart.
8. Why type hints don't protect you, and what you use instead at system boundaries.
9. The difference between `is` and `==`, and when each is correct.
10. What a generator gives you that a list doesn't, and what it costs you.

**Practical:**

11. All six exercises pass.
12. You've broken `chunker.py` in all five ways listed and can explain each failure.

If you stumble on 6, 7, or 8 — go back. Those three are load-bearing for the rest of the
book.

---

## 2.24 · Going deeper (optional)

**If you want one book:** *Fluent Python* (Ramalho). Written for exactly your situation —
experienced programmers learning what makes Python *Python*, rather than beginners learning
to program. Chapters 1, 5, 17 and 21 map directly onto this chapter.

**If you want to understand the data model:** search for "Python Data Model" in the language
reference and read about dunder methods. Understanding that `len(x)` *is* `x.__len__()`,
that `a + b` *is* `a.__add__(b)`, and that this is true uniformly, is the moment Python
stops feeling arbitrary.

**If async still feels shaky:** it's the most important section here, and shakiness now
becomes real pain in Chapter 6. Write a script that fetches 20 URLs three ways — sequential
`await` in a loop, `gather`, and `gather` with a `Semaphore(5)` — and time all three. Ten
minutes of that teaches more than any amount of reading.

**If you want to feel the speed difference:** write the same tight numeric loop in Dart and
Python and time both. Watching Python be 60× slower is useful — it calibrates your instinct
for when to reach for NumPy or push work into a library, which is a judgment you'll need in
Part III.

---

<div align="center">

**[← Chapter 1](../ch01-orientation/)** · **[The Book](../../readme.md)** · **[Chapter 3 → The Modern Toolchain](../ch03-modern-toolchain/)**

*Chapter 2 of 31 · Week 1*

</div>
