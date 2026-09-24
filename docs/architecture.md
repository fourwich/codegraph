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
3. **Decisions** — Extracted from commit messages, ADRs, and CHANGELOG, linked to the exact code lines they justify

---

## Architecture

```
Source files (.ts / .py)  ──▶  tree-sitter parsers  ──▶  CodeNode + Edge
                                                              │
Git history (all commits) ──▶  GitHistory          ──▶  SQLite / Dgraph
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
- **Decision** — `content, reason, alternatives, status, source, source_ref, timestamp, author, constraints, confidence`

---

## Seven commands

| Command | Purpose |
|---|---|
| `codegraph index <path>` | Parse + ingest Git history + store |
| `codegraph why <file>:<line>` | Decision card for that line |
| `codegraph graph --at <date>` | Code graph at a past moment |
| `codegraph decisions --timeline` | Decision evolution chain |
| `codegraph conflicts` | Detect contradictory decisions |
| `codegraph export --for-ai` | Export AI agent context |
| `codegraph serve` | Local web visualization |

---

## Tech choices

| Layer | Choice | Reason |
|---|---|---|
| Parsing | tree-sitter | Multi-language, incremental, industry standard |
| Git | GitPython | Read-only access to real Git history |
| Graph DB | Dgraph | Native graph queries for multi-hop decision tracing |
| CLI | Typer + Rich | Fast CLI, readable terminal output |
| Models | pydantic | Typed data models |
| Storage | SQLite | Default backend; zero-config, local-first |

---

## Status (as of submission)

Numbers below match a local run of `pytest -q` and `codegraph --help` on the same commit.

| Status | Item |
|---|---|
| ✅ Done | Product site (HTML / CSS / JS) |
| ✅ Done | CLI with 7 commands (`index` / `why` / `graph` / `decisions` / `conflicts` / `export` / `serve`) |
| ✅ Done | tree-sitter parsing for TypeScript, Python, Java, Go, Rust, C++ |
| ✅ Done | SQLite storage |
| ✅ Done | Real Git history traversal |
| ✅ Done | Decision extraction from commits, ADRs, CHANGELOG |
| ✅ Done | Real time-travel queries (`graph --at`) |
| ✅ Done | 49 tests passing (`pytest -q`) |
| ✅ Done | Local web visualization (`codegraph serve`) |
| ✅ Done | VSCode extension sources + `why --json` |
| ✅ Done | Optional Ollama LLM extraction hook (`--use-llm`) |
| 🚧 In progress | Dgraph backend (client + `--backend dgraph` implemented; live cluster optional) |
| ⬜ Planned | Dgraph multi-hop query hardening |
| ⬜ Planned | VS Code Marketplace publish |

---

## Roadmap

| Version | Scope |
|---|---|
| v0.1.0 | Stabilize CLI + SQLite + tests |
| v0.2.0 | Dgraph production hardening |
| v0.3.0 | Richer conflict rules |
| v0.4.0 | Marketplace release for VSCode extension |
| v0.5.0 | Larger-repo performance tuning |

---

Built by a 15-year-old self-taught developer.
MIT License. https://github.com/fourwich/codegraph
