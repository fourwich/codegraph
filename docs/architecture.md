# CodeGraph — Architecture Overview

**Git blame tells you who changed it. CodeGraph tells you why.**

---

## Problem

Developers constantly ask "why is this code written this way?" git blame shows
authorship. GitHub search shows text matches. ADR tools require manual writing.
AI coding assistants see only the current file. No existing tool connects a line
of code to the design decisions that shaped it.

---

## Solution — three layers, one graph

1. **Structure** — tree-sitter parses TypeScript/Python into AST nodes and edges (`uses` / `defined_by` / `contains`)
2. **Time** — Every node carries `valid_from` / `valid_to`, derived from real Git history
3. **Decisions** — Extracted from commit messages, ADRs, and CHANGELOG, linked to code lines where a real diff overlap exists. Every record carries a **tier**: `decision` (it states a reason or a rejected alternative) or `event` (plain history). Only decisions are shown by default.

---

## Architecture

```
Source files (.ts / .py)  ──▶  tree-sitter parsers  ──▶  CodeNode + Edge
                                                              │
Git history (all commits) ──▶  GitHistory          ──▶  SQLite
                                                              │
Commit msgs / ADRs / CHANGELOG ──▶  Decision extractor
                                                              │
                                          CLI: index / why / graph / …
                                                              │
                            Terminal card + Web viz + AI context pack
```

---

## Data model

- **CodeNode** — `uid, kind, name, file_path, line_start, line_end, language, valid_from, valid_to, parent_uid`
- **Edge** — `from_uid, to_uid, kind` (`uses` / `defined_by` / `contains`)
- **decision_code_links** — decision_uid / node_uid / file_path / line / commit_sha
- **Decision** — `content, reason, alternatives, status, source, source_ref, timestamp, author, constraints, confidence, category, tier`

`tier` separates records that carry a rationale (`decision`) from plain history
(`event`). `why`, `decisions`, `conflicts`, `export`, `graph` and the web API show
decisions only; `--include-events` adds history, `--include-dependency` adds
dependency records.

---

## Binding a decision to code

`decision_code_links` is what makes `why` work, so it is deliberately narrow:

- **Commit decisions** bind to the changed lines of their commit that land inside
  a CodeNode. A decision claiming more than 10 files or 250 lines is dropped from
  line binding and stays reachable through the commit-level fallback instead — a
  commit that touched half the repository is not a fact about one line.
- **Prose decisions** (ADRs, CHANGELOG) have no commit of their own. They bind to
  the code they name, in order of precision:
  1. an explicit declaration — `governs: src/app.py, src/pkg/` in the front
     matter, or `<!-- governs: src/app.py -->` in the body;
  2. a backticked source path that exists in the graph;
  3. a backticked identifier that matches a real node name **and** is distinctive
     (CamelCase, snake_case, or at least 10 characters) and appears in at most
     three files.

  `why` treats "linked to the symbol covering this line" as line level, so a
  governed file answers for every symbol inside it.

`codegraph why` and the web API share this resolution — the UI calls the same
loader — so they cannot disagree about whether a decision exists for a line. The
web scope filter likewise matches on a path boundary and includes decisions that
govern the scoped code, and it never widens a scope to fill the result.

Conflict detection works on the same principle: opposite terms are matched on word
boundaries, two decisions must be in the same file (or the same folder *and*
share vocabulary), and the generic pairs (`add`/`remove`, `keep`/`drop`) only
count when the two decisions really are about the same thing. A temporal conflict
additionally requires opposite terms — being close in time is not a contradiction.

---

## Eight commands

| Command | Purpose |
|---|---|
| `codegraph index <path>` | Parse + ingest Git history + store |
| `codegraph why <file>:<line>` | Decision card for that line |
| `codegraph graph --at <date>` | Code graph at a past moment |
| `codegraph decisions --timeline` | Decision evolution chain |
| `codegraph conflicts` | Detect contradictory decisions |
| `codegraph export --for-ai` | Export AI agent context |
| `codegraph serve` | Local web visualization |
| `codegraph diff <from> <to>` | Decision changes between two versions |

---

## Tech choices

| Layer | Choice | Reason |
|---|---|---|
| Parsing | tree-sitter | Multi-language, incremental, industry standard |
| Git | GitPython | Read-only access to real Git history |
| CLI | Typer + Rich | Fast CLI, readable terminal output |
| Models | pydantic | Typed data models |
| Storage | SQLite | Default backend; zero-config, local-first |

---

## Status (as of submission)

Numbers below match a local run of `pytest -q` and `codegraph --help` on the same commit.

| Status | Item |
|---|---|
| ✅ Done | Product site (HTML / CSS / JS) |
| ✅ Done | CLI with 8 commands (`index` / `why` / `graph` / `decisions` / `conflicts` / `export` / `serve` / `diff`) |
| ✅ Done | tree-sitter parsing for TypeScript, JavaScript, Python, Java, Go, Rust, C++ |
| ✅ Done | SQLite storage |
| ✅ Done | Real Git history traversal |
| ✅ Done | Decision extraction from commits, ADRs, CHANGELOG, with a `decision` / `event` tier |
| ✅ Done | ADR / CHANGELOG decisions bound to the code they declare with `governs:` |
| ✅ Done | Real time-travel queries (`graph --at`) |
| ✅ Done | 136 tests passing (`pytest -q`, 82% coverage of `src/codegraph`) |
| ✅ Done | Local web visualization (`codegraph serve`) |
| ✅ Done | CLI output contract for editors: `--json` keeps stdout pure, `why` accepts absolute paths |
| ✅ Done | VSCode extension + `why --json` (vsix installable) |
| ✅ Done | Optional Ollama LLM extraction hook (`--use-llm`) |
| ⬜ Planned | VS Code Marketplace publish |
| ⬜ Removed | Dgraph backend — see [ADR-006](adr/006-drop-dgraph-backend.md); revisit only when a shipped query needs multi-hop traversal |

---

## Roadmap

| Version | Scope |
|---|---|
| v0.1.0 | Stabilize CLI + SQLite + tests |
| v0.2.0 | Decision tiers, governed binding, conflict precision |
| v0.3.0 | Richer conflict rules |
| v0.4.0 | Marketplace release for VSCode extension |
| v0.5.0 | Larger-repo performance tuning |

---

Built by a 15-year-old self-taught developer.
MIT License. https://github.com/fourwich/codegraph
