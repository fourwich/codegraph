"""Benchmark helpers: synthesize a fake repo of Python files."""

from __future__ import annotations

import argparse
import time
from pathlib import Path


def generate_repo(root: Path, file_count: int) -> None:
    """Write file_count simple Python modules under root."""
    root.mkdir(parents=True, exist_ok=True)
    for i in range(file_count):
        path = root / f"mod_{i:05d}.py"
        path.write_text(
            f"def helper_{i}():\n    return {i}\n\n" + f"def main_{i}():\n    return helper_{i}()\n",
            encoding="utf-8",
        )


def main() -> None:
    """CLI: generate files and time a codegraph index via library API."""
    parser = argparse.ArgumentParser(description="CodeGraph index benchmark")
    parser.add_argument("--files", type=int, default=1000)
    parser.add_argument("--out", type=Path, default=Path("bench_repo"))
    args = parser.parse_args()

    generate_repo(args.out, args.files)
    start = time.perf_counter()
    from codegraph.commands.index import _ingest_working_tree, write_sqlite_graph
    from codegraph.decisions.sources import extract_all

    nodes: list = []
    edges: list = []
    _ingest_working_tree(args.out.resolve(), nodes, edges)
    decisions = extract_all(args.out.resolve(), depth=20)
    db = args.out / ".codegraph" / "graph.db"
    write_sqlite_graph(db, nodes, edges, decisions)
    elapsed = time.perf_counter() - start
    print(f"files={args.files} nodes={len(nodes)} edges={len(edges)} seconds={elapsed:.3f}")
    print(f"sqlite_bytes={db.stat().st_size if db.exists() else 0}")


if __name__ == "__main__":
    main()
