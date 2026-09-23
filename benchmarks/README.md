# Benchmarks

## Goals

- 1000 files index < 30s
- 10000 files index < 5min
- `why` P99 < 50ms
- `graph --at` P99 < 200ms
- memory < 2GB for 10k files (working-tree mode)

## Run

```bash
.venv\Scripts\python.exe benchmarks\bench_index.py --files 1000 --out bench_repo
.venv\Scripts\python.exe benchmarks\bench_query.py --root . --iterations 200
```

## Notes

This repository (multi-commit Python/TS/HTML) indexes ~244 node versions quickly.
Use `bench_index.py` for synthetic scale tests on your machine.
