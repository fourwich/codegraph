# ADR-006: Drop the Dgraph backend

<!-- governs: src/codegraph/ -->

## Status

Accepted (supersedes the "keep an optional Dgraph backend behind `--backend dgraph`"
clause of [ADR-001](001-use-sqlite-default.md))

## Context

ADR-001 chose SQLite as the default store and kept a Dgraph backend behind a
flag "because a native graph database is the right long-term store for multi-hop
queries". The flag shipped; the backend did not.

An audit of the shipped code found:

- 503 lines in `src/codegraph/graph/` with one unit test per serializer and no
  test that ever reaches a live cluster; the network paths were never executed.
- `graph --backend dgraph` printed the bundled sample decisions rather than the
  Dgraph result, so the flag reported data that did not come from Dgraph.
- `serve --backend dgraph` validated the flag, logged it, and then dropped it —
  the API always queried SQLite.
- `export --for-ai --backend dgraph` raised `AttributeError` on every call.
- `pydgraph` was a hard dependency, and running any of it needed Docker.

No command in the CLI performs a multi-hop query, so nothing consumed the
capability the backend existed for.

## Decision

Remove the Dgraph backend and the `--backend` flag from every command. Delete
`src/codegraph/graph/`, `docker-compose.yml`, `.env.example`, the Dgraph tests
and the `pydgraph` dependency. SQLite at `.codegraph/graph.db` is the only store.

A native graph backend is reconsidered when a shipped query actually needs
multi-hop traversal — not before.

## Consequences

- `--backend dgraph` is gone rather than silently wrong; scripts that passed it
  now fail loudly on an unknown option.
- 503 lines of unexecuted code and one Docker-only dependency are gone.
- The claim and the code agree again: one local store, no optional cluster.
- ADR-001's SQLite decision stands; only its optional-backend clause is retracted.
