---
name: codegraph-why
description: >-
  Answer "why is this line written this way?" from the repository's own decision
  records (ADRs, changelogs, commit messages). Use before editing unfamiliar code,
  or when a value looks arbitrary. Accepts a path:line or a symbol name.
---

# codegraph-why

Answer "why is this line written this way?" from the records the project itself
wrote down, instead of guessing from the code.

## When to use this

- Before editing code you did not write.
- When a value or structure looks arbitrary (`retryLimit = 3`, a 200ms timeout, an
  unusual ordering).
- When the user asks "why does this do X" about code, rather than "what does it do".

## Setup

```bash
pip install codegraphx
codegraph index . --depth 50
```

`--depth` is how far back the git history is read; deeper finds older decisions and
takes longer. The database lands in `.codegraph/graph.db`. Run this once per
repository — `why` reports no record until the repository is indexed.

## Two ways to ask

**By location** — the precise form:

```bash
codegraph why src/codegraph/storage.py:200
```

**By symbol name** — when you know the function, not the line:

```bash
codegraph why insert_nodes
```

The symbol form resolves to the innermost live definition and prints it, so you can
see which one was chosen. If the name does not exist, the error suggests close
matches:

```
Cannot parse location 'insert'. ... Did you mean: insert_edges, insert_nodes, insert_decisions?
```

Names are matched exactly. A near miss is never silently accepted — a fuzzy match
would return the wrong symbol and the card alone would not reveal it.

A symbol has no path to carry its repository, so querying one from outside its
repository needs `--root`:

```bash
codegraph why make_response --root ../flask
```

`path:line` does not need it: an absolute path already names the repository, and a
relative one is resolved by walking up.

## Reading the answer

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

**`binding`** tells you how the record was matched:

| binding | meaning |
|---|---|
| `line` | a record bound to this exact line — the strongest answer |
| `file` | nothing bound to the line; these records concern the file |
| `commit` | matched through the commit that touched the line |
| `dir` | concerns the surrounding directory — weakest, use with care |
| `none` | no record |

**`found: false` is a real answer.** CodeGraph only shows a decision card when the
record states a reason or a rejected alternative. A project that never wrote down its
rationale produces no cards — that is the honest result, not a tool failure. Say so,
rather than inventing a plausible reason.

## Flags

| flag | effect |
|---|---|
| `--json` | machine-readable payload, for scripting or an editor |
| `--include-events` | also show plain history (commit subjects, changelog lines) |
| `--include-dependency` | also show dependency-bump decisions |

`--json` returns `{ file, line, node, decisions, binding, related }`. It exits 1 when
no decision matched, so a script can branch on the code without parsing text.

## Going further

```bash
codegraph decisions --file src/storage.py --timeline   # how a file's decisions evolved
codegraph decisions --timeline                         # the whole repository, oldest first
codegraph conflicts --scope src                        # decisions that contradict each other
codegraph graph --at 2026-09-28 --scope src            # the code graph as of a past date
codegraph export --for-ai --scope src                  # a context pack for a larger review
```

`decisions --timeline` is the one to reach for when the question is "how did this file
get to its current shape" rather than "why does this one line exist".

## Limits worth stating to the user

- **Coverage is partial.** Measured on seven real repositories, 12–40% of sampled
  lines returned a line-level card. A changelog entry links to one line, not to every
  line it influenced; the file-level fallback covers part of that gap.
- **A root-level file gets no directory fallback.** The root is not a subject area, so
  `why LICENSE:1` correctly reports no record.
- **A shallow clone carries only recent history**, so older decisions are absent.
- **Seven languages:** Python, TypeScript, JavaScript, Java, Go, Rust, C++.
- **Indexing is a prerequisite, not automatic.** An unindexed repository reports no
  record for everything, which reads like a broken tool rather than a missing step.

When the answer is no record, report that plainly. The value of this tool is that it
does not fabricate an explanation.
