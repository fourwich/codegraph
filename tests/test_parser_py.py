"""Python parser tests using fixture sample.py."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.treesitter_py import PythonParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"


def test_py_extracts_functions_and_class() -> None:
    parser = PythonParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    kinds = {n.kind for n in nodes}
    assert "add" in names
    assert "multiply" in names
    assert "Calculator" in names
    assert "class" in kinds
    assert "function" in kinds
    functions = [n for n in nodes if n.kind == "function"]
    assert len(functions) >= 3


def test_py_extracts_call_edges() -> None:
    parser = PythonParser()
    nodes = parser.parse_file(FIXTURE)
    edges = parser.extract_edges(nodes)
    uses = [e for e in edges if e.kind == "uses"]
    pairs = {(e.from_uid, e.to_uid) for e in uses}
    by_name = {n.name: n for n in nodes}
    assert (by_name["multiply"].uid, by_name["add"].uid) in pairs
    assert (by_name["compute"].uid, by_name["multiply"].uid) in pairs
