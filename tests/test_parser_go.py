"""Go parser tests using fixture sample.go."""

from __future__ import annotations

from pathlib import Path

from _parser_helpers import by_name, uses_pairs

from codegraph.parser.treesitter_go import GoParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.go"

TYPES = """package calc

type Calculator struct {
	value int
}

func (c *Calculator) Add(n int) int {
	return c.value + n
}

func (c Calculator) Double() int {
	return c.Add(c.value)
}

func run() int {
	c := Calculator{}
	return c.Double()
}
"""


def test_go_extracts_functions() -> None:
    """Parser should find add/multiply."""
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


def test_go_type_declaration_is_a_node() -> None:
    """`type Calculator struct {}` is a class node."""
    nodes = GoParser().parse_text("calc.go", TYPES)
    assert by_name(nodes, "Calculator").kind == "class"


def test_go_methods_belong_to_their_receiver_type() -> None:
    """Pointer and value receivers both resolve to the declared type."""
    parser = GoParser()
    nodes = parser.parse_text("calc.go", TYPES)
    calculator = by_name(nodes, "Calculator")

    assert by_name(nodes, "Add").parent_uid == calculator.uid
    assert by_name(nodes, "Double").parent_uid == calculator.uid
    kinds = [e.kind for e in parser.extract_edges(nodes)]
    assert kinds.count("contains") == 2


def test_go_method_calls_resolve() -> None:
    """A method calling another method on the same type produces edges."""
    parser = GoParser()
    edges = parser.extract_edges(parser.parse_text("calc.go", TYPES))
    assert ("Double", "Add") in uses_pairs(edges)
