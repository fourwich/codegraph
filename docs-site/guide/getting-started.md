# Getting started

CodeGraph answers **why is this line here?** by joining:

1. Structure (tree-sitter AST + call edges)
2. Time (Git history / `valid_from` / `valid_to`)
3. Decisions (commits, ADRs, CHANGELOG)

## Install

See [Installation](./installation).

## First commands

```bash
codegraph index . --depth 50
codegraph why path/to/file.py:12
codegraph graph --at 2026-09-23 --scope src
```
