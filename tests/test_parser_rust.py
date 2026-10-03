"""Rust parser tests using fixture sample.rs."""

from __future__ import annotations

from pathlib import Path

from _parser_helpers import by_name

from codegraph.parser.treesitter_rust import RustParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample.rs"


def test_rust_extracts_functions() -> None:
    """Parser should find add/multiply/compute."""
    parser = RustParser()
    nodes = parser.parse_file(FIXTURE)
    names = {n.name for n in nodes}
    assert "add" in names
    assert "multiply" in names
    assert "compute" in names


def test_rust_extracts_call_edges() -> None:
    """Both call sites resolve into uses edges."""
    parser = RustParser()
    nodes = parser.parse_file(FIXTURE)
    uses = [e for e in parser.extract_edges(nodes) if e.kind == "uses"]
    assert len(uses) == 2


def test_rust_impl_methods_belong_to_their_type() -> None:
    """`impl Calculator { fn compute }` links compute to Calculator."""
    parser = RustParser()
    nodes = parser.parse_file(FIXTURE)
    compute = by_name(nodes, "compute")
    calculator = by_name(nodes, "Calculator")

    assert compute.parent_uid == calculator.uid
    kinds = [e.kind for e in parser.extract_edges(nodes)]
    assert kinds.count("contains") == 1
    assert kinds.count("defined_by") == 1


def test_rust_impl_of_a_trait_points_at_the_type() -> None:
    """`impl Scale for Meter` attaches its methods to Meter, not to Scale."""
    source = (
        "trait Scale {\n    fn scale(&self, n: i32) -> i32;\n}\n\n"
        "struct Meter { value: i32 }\n\n"
        "impl Scale for Meter {\n    fn scale(&self, n: i32) -> i32 {\n"
        "        self.value * n\n    }\n}\n"
    )
    nodes = RustParser().parse_text("meter.rs", source)
    meter = next(n for n in nodes if n.name == "Meter")
    impl_scale = [n for n in nodes if n.name == "scale" and n.line_start > meter.line_start]

    assert impl_scale and impl_scale[0].parent_uid == meter.uid
