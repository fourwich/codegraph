# First index

```bash
codegraph index . --depth 50
```

Walks the last N commits, versions CodeNodes with `valid_from` / `valid_to`, and extracts decisions.

Output includes commits walked, nodes, edges, and decisions stored under `.codegraph/graph.db`.
