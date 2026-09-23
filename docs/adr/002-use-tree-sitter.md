# ADR-002: tree-sitter for code parsing

## Status

Accepted

## Context

CodeGraph must extract functions, classes, and call edges from TypeScript and Python. Hand-written parsers break on real syntax. We chose tree-sitter instead of a single-language AST library because multi-language support is a core differentiator.

## Decision

Parse sources with tree-sitter (`tree-sitter-typescript`, `tree-sitter-python`). Keep a `BaseParser` interface so Java/Go/Rust can be added without touching the storage layer.

## Consequences

- Solid AST for modern syntax without maintaining grammars ourselves.
- Call edges use name matching (not full type inference) in v0.1.
- Binaries come from the `tree-sitter` package ecosystem; versions are pinned in `pyproject.toml`.

## Alternatives

- libcst / ast for Python only (rejected: no TypeScript).
- Joern/CodeQL (rejected: heavy toolchain for a student MVP).
