"""C++ parser tests using fixture sample.cpp."""

from __future__ import annotations

from pathlib import Path

from _parser_helpers import by_name, uses_pairs

from codegraph.parser.treesitter_cpp import CppParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.cpp"


def _nodes(parser: CppParser, path: Path = FIXTURE):
    return parser.parse_file(path)


def test_cpp_extracts_functions() -> None:
    """Parser should find add/multiply."""
    nodes = _nodes(CppParser())
    names = {n.name for n in nodes}
    assert "add" in names
    assert "multiply" in names


def test_cpp_extracts_in_class_method() -> None:
    """An in-class method is a node, not just its class."""
    nodes = _nodes(CppParser())
    assert "compute" in {n.name for n in nodes}
    assert by_name(nodes, "compute").kind == "function"


def test_cpp_links_method_to_its_class() -> None:
    """Methods hang off the class, so hierarchy edges exist."""
    parser = CppParser()
    nodes = _nodes(parser)
    compute = by_name(nodes, "compute")
    calculator = by_name(nodes, "Calculator")

    assert compute.parent_uid == calculator.uid
    kinds = [e.kind for e in parser.extract_edges(nodes)]
    assert kinds.count("contains") == 1
    assert kinds.count("defined_by") == 1


def test_cpp_resolves_calls_from_a_method() -> None:
    """Both call sites resolve; the in-class one used to be dropped."""
    parser = CppParser()
    edges = parser.extract_edges(_nodes(parser))

    assert uses_pairs(edges) == {("multiply", "add"), ("compute", "multiply")}


def test_cpp_prototype_is_a_function_but_a_variable_is_not() -> None:
    """`int helper(int);` declares a function; `int limit = 3;` does not."""
    source = "int helper(int x);\nint limit = 3;\nint use(void) { return helper(limit); }\n"
    nodes = CppParser().parse_text("decls.cpp", source)
    names = {n.name for n in nodes}

    assert by_name(nodes, "helper").kind == "function"
    assert "limit" not in names
    assert by_name(nodes, "use").kind == "function"


def test_cpp_class_prototype_and_definition_both_named() -> None:
    """`int spin(int)` in a class body and `int W::spin(int)` are both named."""
    source = "class W {\npublic:\n    int spin(int n);\n};\nint W::spin(int n) { return n; }\n"
    nodes = CppParser().parse_text("w.cpp", source)

    assert [n.name for n in nodes].count("spin") == 2
