"""Structure tests for Dgraph mutation builders (no live Dgraph)."""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.graph.mutations import build_decision_json, build_edge_json, build_node_json
from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus, Edge


def _node() -> CodeNode:
    return CodeNode(
        uid="src/a.py::function::foo@1",
        kind="function",
        name="foo",
        file_path="src/a.py",
        line_start=1,
        line_end=5,
        language="python",
    )


def _edge() -> Edge:
    return Edge(
        from_uid="src/a.py::function::foo@1",
        to_uid="src/a.py::function::bar@6",
        kind="uses",
        file_path="src/a.py",
        line=3,
    )


def _decision() -> Decision:
    return Decision(
        uid="dec-001",
        content="Use pytest",
        reason="Built-in runner is limited",
        alternatives=["unittest"],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ADR,
        source_ref="ADR-001",
        timestamp=datetime(2024, 11, 2, tzinfo=timezone.utc),
        author="dev@example.com",
        file_path="src/a.py",
        line=1,
        constraints=["Keep tests fast"],
        confidence=0.9,
    )


def test_build_node_json_has_required_fields() -> None:
    """build_node_json should include core CodeNode predicates."""
    payload = build_node_json(_node())
    for key in (
        "node_uid",
        "kind",
        "name",
        "file_path",
        "line_start",
        "line_end",
        "language",
        "valid_from",
    ):
        assert key in payload
    assert payload["name"] == "foo"
    assert payload["line_start"] == 1


def test_build_edge_json_links_from_to() -> None:
    """build_edge_json should resolve predicate and both endpoint uids."""
    payload = build_edge_json(_edge(), "A", "B")
    assert payload["from_uid"] == "A"
    assert payload["to_uid"] == "B"
    assert payload["predicate"] == "uses"
    assert payload["line"] == 3


def test_build_decision_json_with_target() -> None:
    """Decision JSON should carry justifies target when provided."""
    payload = build_decision_json(_decision(), "node-1")
    assert payload["content"] == "Use pytest"
    assert payload["status"] == "accepted"
    assert payload["justifies_uid"] == "node-1"
    assert payload["confidence"] == 0.9


def test_build_decision_json_without_target() -> None:
    """Decision JSON should omit justifies_uid when target is None."""
    payload = build_decision_json(_decision(), None)
    assert "justifies_uid" not in payload
    assert payload["decision_uid"] == "dec-001"
    assert payload["alternatives"] == ["unittest"]
