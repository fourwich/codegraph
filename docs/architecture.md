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

| Status | Item |
|---|---|
| ✅ Done | Product site (HTML / CSS / JS) |
| ✅ Done | CLI with 6 commands |
| ✅ Done | tree-sitter parsing for TypeScript, Python, Java, Go, Rust, C++ |
| ✅ Done | SQLite storage |
| ✅ Done | Real Git history traversal |
| ✅ Done | Decision extraction from commits, ADRs, CHANGELOG |
| ✅ Done | Real time-travel queries (`graph --at`) |
| ✅ Done | 48 tests passing |
| ✅ Done | Local web visualization (Cytoscape.js) |
| ✅ Done | VSCode extension (source + vsix) |
| ✅ Done | Optional LLM extraction (Ollama, graceful fallback) |
| 🚧 In progress | Dgraph backend (client ready; live cluster optional) |
| ⬜ Planned | Deeper multi-hop Dgraph queries |

---

## Roadmap

| Version | Scope |
|---|---|
| v0.1.0 | CLI + SQLite + real Git history + decision extraction (current) |
| v0.2.0 | Multi-language parsers + time-travel queries |
| v0.3.0 | Web visualization + export / conflicts |
| v0.4.0 | Dgraph backend hardening |
| v0.5.0 | LLM-based decision extraction (local-first, Ollama) |
| v0.6.0 | VSCode extension marketplace publish |

---

Built by a 15-year-old self-taught developer.
MIT License. https://github.com/fourwich/codegraph
