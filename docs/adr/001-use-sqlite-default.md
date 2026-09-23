# ADR-001: SQLite as the default graph store

## Status

Accepted

## Context

CodeGraph needs a local store for CodeNodes and Edges during the MVP. Judges and developers must run the CLI without operating a database server. Multi-hop graph queries matter later, but day-one reliability and zero setup matter more.

## Decision

Use SQLite (stdlib `sqlite3`) as the default backend under `.codegraph/graph.db`. Keep an optional Dgraph backend behind `--backend dgraph` because a native graph database is the right long-term store for multi-hop queries.

## Consequences

- Install and demos work offline with no Docker.
- Schema migrations must be lightweight (`ALTER TABLE` when columns are added).
- Switching backends later is a CLI flag, not a rewrite of parsers.

## Alternatives

- Dgraph first (rejected for MVP: requires Docker and ops setup).
- In-memory only (rejected: cannot time-travel after the process exits).
