"""Tests for working-tree ingest helpers."""

from __future__ import annotations

from pathlib import Path

from codegraph.commands.index import _ingest_working_tree


def test_ingest_working_tree(tmp_path: Path) -> None:
    """Working-tree ingest collects Python nodes."""
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    nodes: list = []
    edges: list = []
    _ingest_working_tree(tmp_path, nodes, edges)
    assert any(n.name == "f" for n in nodes)
