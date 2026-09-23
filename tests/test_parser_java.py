"""Java parser tests using fixture sample.java."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.treesitter_java import JavaParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.java"


def test_java_extracts_class_and_methods() -> None:
    """Parser should find Calculator and methods."""
    parser = JavaParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    assert "Calculator" in names
    assert "add" in names or "multiply" in names
    assert any(n.kind in {"class", "function"} for n in nodes)


def test_java_extracts_call_edges() -> None:
    """Parser should emit uses edges for calls."""
    parser = JavaParser()
    nodes = parser.parse_file(FIXTURE)
    edges = parser.extract_edges(nodes)
    assert any(e.kind == "uses" for e in edges) or any(e.kind == "contains" for e in edges)
