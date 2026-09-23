# Backends

## SQLite (default)

Zero-ops local store at `.codegraph/graph.db`. Best for demos and CI.

## Dgraph (optional)

Multi-hop native graph queries.

```bash
docker compose up -d
codegraph index . --backend dgraph
codegraph why file.py:10 --backend dgraph
```

Connection failures exit with code `3`.
