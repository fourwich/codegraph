"""Binding decisions to the code they describe."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from codegraph.commands.index import (
    bind_decisions_to_lines,
    cap_links,
    is_distinctive_identifier,
    parse_governs,
)
from codegraph.models import CodeNode, Decision, DecisionSource, DecisionTier

TS = datetime(2026, 9, 24, tzinfo=timezone.utc)


def _node(uid: str, name: str, path: str, start: int, end: int) -> CodeNode:
    return CodeNode(
        uid=uid,
        kind="function",
        name=name,
        file_path=path,
        line_start=start,
        line_end=end,
        language="python",
    )


def _adr_decision(path: str = "docs/adr/001-x.md") -> Decision:
    return Decision(
        uid="d1",
        content="Use X as the default store",
        reason="because setup must stay zero",
        status="accepted",
        source=DecisionSource.ADR,
        source_ref="ADR 001",
        timestamp=TS,
        file_path=path,
        tier=DecisionTier.DECISION,
    )


def test_parse_governs_reads_both_forms() -> None:
    assert parse_governs("<!-- governs: src/a.py, src/b/ -->") == ["src/a.py", "src/b/"]
    assert parse_governs("governs: src/a.py") == ["src/a.py"]
    assert parse_governs("nothing here") == []


def test_governs_marker_binds_a_decision_to_its_file(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "001-x.md").write_text(
        "# ADR 001\n\n<!-- governs: src/app.py -->\n\n## Decision\nUse X because Y.\n",
        encoding="utf-8",
    )
    nodes = [_node("n1", "f", "src/app.py", 10, 20), _node("n2", "g", "other.py", 1, 5)]

    links = bind_decisions_to_lines(tmp_path, [_adr_decision()], nodes)

    assert links == [("d1", "n1", "src/app.py", 10)]


def test_governs_directory_covers_the_files_inside(tmp_path: Path) -> None:
    adr = tmp_path / "docs"
    adr.mkdir(parents=True)
    (adr / "a.md").write_text(
        "# ADR\n\n<!-- governs: src/pkg/ -->\n\n## Decision\nUse X because Y.\n",
        encoding="utf-8",
    )
    nodes = [
        _node("n1", "f", "src/pkg/one.py", 1, 5),
        _node("n2", "g", "src/pkg/two.py", 3, 9),
        _node("n3", "h", "src/elsewhere.py", 1, 5),
    ]

    links = bind_decisions_to_lines(tmp_path, [_adr_decision("docs/a.md")], nodes)

    assert sorted(item[2] for item in links) == ["src/pkg/one.py", "src/pkg/two.py"]


def test_backticked_path_binds_even_without_a_marker(tmp_path: Path) -> None:
    decision = _adr_decision()
    decision.reason = "See `src/app.py` for the store implementation."
    nodes = [_node("n1", "f", "src/app.py", 4, 8)]

    links = bind_decisions_to_lines(tmp_path, [decision], nodes)

    assert links == [("d1", "n1", "src/app.py", 4)]


def test_is_distinctive_identifier_filters_prose() -> None:
    assert is_distinctive_identifier("BaseParser")
    assert is_distinctive_identifier("valid_from")
    assert is_distinctive_identifier("authenticate")
    assert not is_distinctive_identifier("index")
    assert not is_distinctive_identifier("decision")


def test_events_are_not_bound_by_prose(tmp_path: Path) -> None:
    """Only decision-tier records are governed; history stays history."""
    adr = tmp_path / "docs"
    adr.mkdir(parents=True)
    (adr / "a.md").write_text(
        "# ADR\n\n<!-- governs: src/app.py -->\n\n## Decision\nUse X.\n", encoding="utf-8"
    )
    event = _adr_decision("docs/a.md")
    event.tier = DecisionTier.EVENT
    nodes = [_node("n1", "f", "src/app.py", 4, 8)]

    assert bind_decisions_to_lines(tmp_path, [event], nodes) == []


def test_cap_links_drops_overbroad_bindings() -> None:
    """A decision claiming 11 files is not a line-level fact."""
    wide = [("d1", f"n{i}", f"f{i}.py", i) for i in range(11)]
    assert cap_links(wide) == []

    narrow = [("d1", f"n{i}", "f.py", i) for i in range(5)]
    assert len(cap_links(narrow)) == 5
