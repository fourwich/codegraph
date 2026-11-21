---
name: codegraph-why
description: Explain why a line of code exists, from the repository's own decision records (ADRs, changelogs, commit messages). Use before changing unfamiliar code, or when asked why something is written a certain way.
---

# codegraph-why

Answer "why is this line written this way?" from the records the project itself
wrote down, instead of guessing from the code.

## When to use this

- Before editing code you did not write.
- When a value or structure looks arbitrary (`retryLimit = 3`, a 200ms timeout, an
  unusual ordering).
- When the user asks "why does this do X" about code, rather than "what does this do".

## Setup

The CLI must be installed once:

```bash
pip install codegraphx
```

Then index the repository you are working in. This is the only step that takes
time (a few seconds per hundred commits):

```bash
codegraph index . --depth 50
```

`--depth` is how far back the git history is read. Deeper finds older decisions and
takes longer. The database lands in `.codegraph/graph.db` inside the repository.

## Asking why

```bash
codegraph why <path>:<line>
```

Real output:

```
┌──── Matched CodeNode ────────────────────────────────┐
│  kind: function   name: insert_nodes                 │
│  range: storage.py:199-223  language: python         │
└──────────────────────────────────────────────────────┘

Query storage.py:200 → 1 matched line-level decision(s)

  Decision #1: Use SQLite (stdlib `sqlite3`) as the store
    [Reason]  CodeGraph needs a local store for CodeNodes and Edges
              during the MVP. Judges and developers must run the CLI
              without operating a database server.
    [Alternatives] · Dgraph first (rejected for MVP: requires Docker)
    [Source]  adr · ADR 001-use-sqlite-default
```

Add `--json` for machine-readable output.

## Reading the answer

**`binding`** tells you how the record was matched:

| binding | meaning |
|---|---|
| `line` | a record bound to this exact line — the strongest answer |
| `file` | nothing bound to the line; these records concern the file |
| `commit` | matched through the commit that touched the line |
| `dir` | concerns the surrounding directory — weakest, use with care |
| `none` | no record |

**`found: false` is a real answer.** CodeGraph only shows a decision card when the
record states a reason or a rejected alternative. A project that never wrote down
its rationale produces no cards — that is the honest result, not a tool failure.
Say so, rather than inventing a plausible reason.

## Related commands

```bash
codegraph decisions --file <path> --timeline   # how a file's decisions evolved
codegraph conflicts --scope <path>             # decisions that contradict each other
codegraph graph --at 2026-09-28 --scope src    # the code graph as of a past date
```

## Limits worth stating to the user

- **Coverage is partial.** Measured on seven real repositories, 12–40% of sampled
  lines returned a line-level card. A changelog entry links to one line, not to
  every line it influenced.
- **A root-level file gets no directory fallback.** The root is not a subject area,
  so `why LICENSE:1` correctly reports no record.
- **A shallow clone carries only recent history**, so older decisions are absent.
- **Seven languages:** Python, TypeScript, JavaScript, Java, Go, Rust, C++.

When the answer is no record, report that plainly. The value of this tool is that
it does not fabricate an explanation.
