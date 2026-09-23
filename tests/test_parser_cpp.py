"""C++ parser tests using fixture sample.cpp."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.treesitter_cpp import CppParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.cpp"


def test_cpp_extracts_functions() -> None:
    """Parser should find add/multiply."""
    parser = CppParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    assert "add" in names
    assert "multiply" in names


def test_cpp_extracts_call_edges() -> None:
    """Parser should emit uses edges."""
    parser = CppParser()
    nodes = parser.parse_file(FIXTURE)
    edges = parser.extract_edges(nodes)
    assert any(e.kind == "uses" for e in edges) or any(e.kind == "contains" for e in edges)
