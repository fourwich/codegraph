# ADR-001: SQLite as the default graph store

<!-- governs: src/codegraph/storage.py -->

## Status

Accepted

## Context

CodeGraph needs a local store for CodeNodes and Edges during the MVP. Judges and developers must run the CLI without operating a database server. Multi-hop graph queries matter later, but day-one reliability and zero setup matter more.

## Decision

Use SQLite (stdlib `sqlite3`) as the store under `.codegraph/graph.db`.

*Superseded clause:* the original text also kept "an optional Dgraph backend
behind `--backend dgraph`". That backend was never completed and was removed in
[ADR-006](006-drop-dgraph-backend.md).

## Consequences

- Install and demos work offline with no Docker.
- Schema migrations must be lightweight (`ALTER TABLE` when columns are added).
- A different store would be a rewrite of `storage.py`, not a CLI flag — see
  ADR-006 for what that costs when the backend does not exist.

## Alternatives

- Dgraph first (rejected for MVP: requires Docker and ops setup).
- In-memory only (rejected: cannot time-travel after the process exits).
