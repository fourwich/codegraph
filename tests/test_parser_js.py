"""JavaScript parser tests using fixture sample.js."""

from __future__ import annotations

from pathlib import Path

from codegraph.parser.treesitter_js import JavaScriptParser
from codegraph.parser.registry import get_parser_for_path, is_supported_source

FIXTURE = Path(__file__).parent / "fixtures" / "sample.js"


def test_registry_supports_js() -> None:
    assert is_supported_source(Path("a.js"))
    assert is_supported_source(Path("a.mjs"))
    assert is_supported_source(Path("a.cjs"))
    assert isinstance(get_parser_for_path(Path("a.js")), JavaScriptParser)


def test_js_extracts_functions() -> None:
    parser = JavaScriptParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    assert "add" in names
    assert "multiply" in names
    assert any(n.kind == "function" for n in nodes)


def test_js_extracts_call_edges() -> None:
    parser = JavaScriptParser()
    nodes = parser.parse_file(FIXTURE)
    edges = parser.extract_edges(nodes)
    uses = [e for e in edges if e.kind == "uses"]
    pairs = {(e.from_uid, e.to_uid) for e in uses}
    by = {n.name: n for n in nodes}
    assert (by["multiply"].uid, by["add"].uid) in pairs
