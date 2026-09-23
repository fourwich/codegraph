"""Go parser tests using fixture sample.go."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.treesitter_go import GoParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.go"


def test_go_extracts_functions() -> None:
    """Parser should find add/multiply/compute."""
    parser = GoParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    assert "add" in names
    assert "multiply" in names


def test_go_extracts_call_edges() -> None:
    """Parser should emit uses edges."""
    parser = GoParser()
    nodes = parser.parse_file(FIXTURE)
    edges = parser.extract_edges(nodes)
    assert any(e.kind == "uses" for e in edges)
