# Benchmarks

Real-repo attempts first, then a synthetic scale test. Numbers come from
`codegraph index` and in-process SQLite queries on this machine.

## Real projects tried

| Project | Clone | Index | Nodes | Edges | Decisions | Notes |
|---|---|---|---|---|---|---|
| sindresorhus/got | depth 300 | 200 commits / 44.1s | 17208 | 43380 | **14** | TypeScript-heavy; decision rules rarely hit |
| expressjs/express | depth 80 | 80 commits / 15.1s | 0 | 0 | **33** | Pure JS — **not in parser set** (ts/py/java/go/rs/cpp) |
| vitejs/vite | depth 300 | timeout | — | — | — | clone timed out |
| fastapi/fastapi | depth 120 | timeout | — | — | — | clone timed out |

None reached **Decisions ≥ 50**, so the case-study path was not used.
Honest gap: JavaScript sources are not parsed yet; many commits also lack
rationale keywords.

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
| Decisions | 102 (100 ADR + 2 from commit text) |

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
```
