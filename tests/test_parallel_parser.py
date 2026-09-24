"""Tests for parallel working-tree parsing."""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.parser.parallel import parse_files_parallel


def test_parse_files_parallel_single_worker() -> None:
    """Single-worker path still returns nodes and edges."""
    items = [
        ("a.py", "def f():\n    return 1\n"),
        ("b.py", "def g():\n    return f()\n"),
    ]
    nodes, edges = parse_files_parallel(
        items,
        commit_sha="abc",
        valid_from=datetime.now(timezone.utc),
        jobs=1,
    )
    names = {n.name for n in nodes}
    assert "f" in names
    assert "g" in names
    assert any(e.kind in {"uses", "contains", "defined_by"} for e in edges)
