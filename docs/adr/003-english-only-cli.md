# ADR-003: English-only user-facing CLI strings

## Status

Accepted

## Context

CodeGraph is submitted to an international competition. Judges read English only. Mixed-language CLI output looks unfinished and breaks screenshots.

## Decision

All user-facing CLI strings, decision cards, and the product site are English. Code comments and docstrings are English. Internal `docs/prompts` may stay bilingual for the maintainer.

## Consequences

- Tests assert English labels such as `[Decision]` and `Invalid argument`.
- Contributors must not reintroduce Chinese in `src/`, `tests/`, or `index.html`.

## Alternatives

- Bilingual CLI (rejected: doubles translation work before the deadline).
