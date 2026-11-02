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


def test_cpp_macro_with_a_body_is_not_a_function() -> None:
    """`TEST(suite, name) { ... }` is a macro invocation, not a function.

    tree-sitter reports it as a function_definition whose name is the macro. Every
    TEST in a file then became a node called "TEST", and because call edges match
    on name those nodes fanned out to each other: on fmt, 1500 nodes produced
    416k edges. C and C++ write macros in full capitals, so an all-caps name is a
    macro.
    """
    source = (
        "TEST(args_test, basic) {\n  int x = 1;\n}\n\n"
        "TEST(args_test, strings) {\n  int y = 2;\n}\n\n"
        "void real_function() {\n  int z = 3;\n}\n"
    )
    nodes = CppParser().parse_text("t.cc", source)
    names = [n.name for n in nodes]

    assert "TEST" not in names, names
    assert "real_function" in names


def test_cpp_macro_does_not_swallow_the_class_beside_it() -> None:
    """Dropping a macro must not drop the real symbols in the same file."""
    source = (
        "SOME_MACRO(x) {\n  return 1;\n}\n\n"
        "class Widget {\n public:\n  void spin();\n};\n\n"
        "void Widget::spin() {}\n"
    )
    nodes = CppParser().parse_text("m.cpp", source)
    names = {n.name for n in nodes}

    assert "SOME_MACRO" not in names
    assert "Widget" in names
    assert "spin" in names


def test_cpp_uppercase_class_is_still_kept() -> None:
    """Only functions are filtered; an all-caps class name is legal C++."""
    source = "class HTTPClient {\n public:\n  void send();\n};\n"
    nodes = CppParser().parse_text("c.cpp", source)

    assert by_name(nodes, "HTTPClient").kind == "class"
    assert by_name(nodes, "send").kind == "function"
