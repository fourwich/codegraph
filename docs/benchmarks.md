# Benchmarks

Real-repo attempts first, then a synthetic scale test. Numbers come from
`codegraph index` and in-process SQLite queries on this machine.

## Real projects tried

| Project | Clone | Index | Nodes | Edges | Decisions | Notes |
|---|---|---|---|---|---|---|
| sindresorhus/got | depth 300 | 200 commits / 44.1s | 17208 | 43380 | **14** | TypeScript-heavy; decision rules rarely hit |
| expressjs/express | depth 200 | 200 commits / ~66s | 5920 | 883 | **5** (of 204 records) | After the 2026 correctness + precision pass; see [case study](case-study.md) |
| vitejs/vite | depth 300 | timeout | — | — | — | clone timed out |
| fastapi/fastapi | depth 120 | timeout | — | — | — | clone timed out |

Express numbers from July 2026: **5920 nodes / 883 edges / 204 records**, of
which **5 are decisions** and 199 are history events. The earlier
"7027 nodes / 1180 edges / 174 decisions" was measured before duplicate node
versions and dangling edges were removed, and before commit subjects stopped
counting as decisions.

`Decisions` counts only records that state a reason or a rejected alternative.
Re-measure any repository with:

```bash
python scripts/eval_decision_precision.py <repo> --depth 200
```

Note: Express uses a commit message style that predates conventional commits, so fewer decisions are extracted than in newer projects. The structural index (nodes/edges) is complete.

## Synthetic repository

- 1000 Python files (5 functions each)
- 500 TypeScript files (5 exported functions each)
- 100 ADR markdown files
- 1 git commit (working-tree parse path)

### Index performance

| Metric | Value |
|---|---|
| Total time | **11.9 s** |
| Commits walked | 1 |
| Nodes | 7500 |
| Edges | 0 (no inter-function calls in the fixture) |
| Decisions | 102 (100 ADR + 2 from commit text) — measured before the tier model |

### Query performance (in-process, 50 runs)

| Query | P50 | P95 | P99 |
|---|---|---|---|
| `why` (find_node_at_line) | 0.35 ms | 0.46 ms | 0.54 ms |
| `graph --at` (query_nodes_at) | 0.42 ms | 0.59 ms | 0.62 ms |
| `conflicts` (detect_all on 102 decisions) | 143 ms | 165 ms | 165 ms |

CLI wall-clock for a single `why` / `graph` / `conflicts` invocation is ~400 ms,
almost entirely Python + Typer process startup.

### Memory

Peak tracemalloc during the query loop: **~0.2 MB** (graph already on disk).
Full index RSS was not sampled separately; wall time 11.9s for 1500 source files.

Hardware: Windows 11, Python 3.12 (`.venv`), local SSD.

## Reproduce

```bash
# synthetic generator used for this run
.venv\Scripts\python.exe submission/video_work/bench_synth.py

# decision precision on any repository
.venv\Scripts\python.exe scripts/eval_decision_precision.py <repo> --depth 200
```

