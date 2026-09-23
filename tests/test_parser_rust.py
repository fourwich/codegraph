"""Rust parser tests using fixture sample.rs."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.treesitter_rust import RustParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.rs"


def test_rust_extracts_functions() -> None:
    """Parser should find add/multiply/compute."""
    parser = RustParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    assert "add" in names
    assert "multiply" in names


def test_rust_extracts_call_edges() -> None:
    """Parser should emit uses edges."""
    parser = RustParser()
    nodes = parser.parse_file(FIXTURE)
    edges = parser.extract_edges(nodes)
    assert any(e.kind == "uses" for e in edges)
