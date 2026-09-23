"""Benchmark why / graph query latency against a local SQLite index."""

from __future__ import annotations

import argparse
import statistics
import time
from datetime import datetime
from pathlib import Path

from codegraph.storage import (
    connect,
    count_edges_at,
    db_path_for_root,
    find_node_at_line,
    query_nodes_at,
)


def percentile(values: list[float], p: float) -> float:
    """Return the p-th percentile (0-100) of values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def bench(path: Path, iterations: int) -> None:
    """Run why and graph timing loops."""
    conn = connect(db_path_for_root(path))
    why_times: list[float] = []
    graph_times: list[float] = []
    at = datetime(2026, 9, 23, 23, 59, 59)
    try:
        for i in range(iterations):
            t0 = time.perf_counter()
            find_node_at_line(conn, "src/codegraph/cli.py", 24 + (i % 5))
            why_times.append((time.perf_counter() - t0) * 1000)
            t1 = time.perf_counter()
            query_nodes_at(conn, at, "src")
            count_edges_at(conn, at, "src")
            graph_times.append((time.perf_counter() - t1) * 1000)
    finally:
        conn.close()

    def report(name: str, xs: list[float]) -> None:
        print(
            f"{name}: p50={percentile(xs, 50):.2f}ms "
            f"p95={percentile(xs, 95):.2f}ms p99={percentile(xs, 99):.2f}ms "
            f"mean={statistics.mean(xs):.2f}ms"
        )

    report("why", why_times)
    report("graph", graph_times)


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="CodeGraph query benchmark")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--iterations", type=int, default=200)
    args = parser.parse_args()
    bench(args.root.resolve(), args.iterations)


if __name__ == "__main__":
    main()
