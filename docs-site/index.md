# CodeGraph

Turn code structure, git history, and design decisions into one queryable graph.

::: tip Why?
Ask **why is this line here?** and get a decision card — not just a blame line.
:::

## Features

- tree-sitter parsing (Python, TypeScript, Java, Go, Rust, C++)
- Real Git time travel (`--at`)
- Decision extraction from commits, ADRs, CHANGELOG
- SQLite default · optional Dgraph backend
- Local Cytoscape visualizer (`codegraph serve`)
- AI context packs (`codegraph export --for-ai`)

## Quick start

```bash
pip install -e ".[dev]"
codegraph index .
codegraph why src/codegraph/cli.py:24
codegraph graph --at 2026-09-23 --scope src
```

## Links

- [GitHub](https://github.com/fourwich/codegraph)
- [Product site](https://fourwich.github.io/codegraph)
