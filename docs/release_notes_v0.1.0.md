# CodeGraph v0.1.0 (alpha)

First public alpha of CodeGraph — a decision memory layer that turns code structure, git history, and design decisions into one queryable graph.

## What's in this release

- Product site (`index.html` / `styles.css` / `main.js`) with a terminal demo and graph hero
- CLI with four commands: `index`, `why`, `graph`, `decisions`
- tree-sitter parsing for TypeScript (`.ts` / `.tsx`) and Python (`.py`)
- SQLite persistence at `.codegraph/graph.db` (default backend)
- Decision cards for `codegraph why <file>:<line>` (location, decision, reason, alternatives, source, status, constraints, confidence)
- Historical snapshot helper `codegraph graph --at YYYY-MM-DD --scope <path>`
- English-only user-facing CLI output
- Sixteen pytest cases covering CLI paths and parser fixtures

Reproduce a local index and try a decision card:

```bash
pip install -e ".[dev]"
codegraph index .
codegraph why src/auth/session.ts:42
```

## Known limitations

- This is **alpha** software and the API may change
- Decision data in the default demo path is bundled sample data, not a full PR/ADR ingest pipeline yet
- Call edges use name matching; there is no full type-aware resolution
- The **Dgraph backend is not complete** and is optional; SQLite remains the supported default
- Commands `conflicts`, `export`, and `serve` are planned and not shipped in v0.1.0

## What's next

- Finish the optional Dgraph backend (multi-hop queries and time-travel filters)
- Detect contradictory accepted decisions
- Local web visualization (Cytoscape.js)
- Context export packs for AI coding agents

Thanks for trying CodeGraph. Issues and PRs are welcome.
