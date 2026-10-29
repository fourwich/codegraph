"""Prose decisions bind to code through the identifiers they name.

A changelog entry says "`redirect` returns 303 instead of 302"; `redirect` is a
function defined in exactly one file, so the decision can bind to it even though
the identifier is lowercase and short. Names that are not unique still require the
distinctive spelling (snake_case / CamelCase / long), which is what keeps prose
words from binding to random symbols.
"""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.commands.index import bind_decisions_to_lines
from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus, DecisionTier


def _node(uid: str, name: str, path: str, start: int = 1, end: int = 10) -> CodeNode:
    return CodeNode(
        uid=uid,
        kind="function",
        name=name,
        file_path=path,
        line_start=start,
        line_end=end,
        language="python",
    )


def _decision(content: str, alternatives: list[str] | None = None) -> Decision:
    return Decision(
        uid="d-prose",
        content=content,
        reason="",
        alternatives=alternatives or [],
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMENT,
        source_ref="CHANGES.rst · Version 3.2.0",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        file_path="CHANGES.rst",
        tier=DecisionTier.DECISION,
    )


def _bound(nodes: list[CodeNode], decision: Decision) -> set[str]:
    links = bind_decisions_to_lines(__import__("pathlib").Path("."), [decision], nodes)
    by_uid = {n.uid: n for n in nodes}
    return {by_uid[uid].name for _d, uid, _p, _l in links if uid in by_uid}


def test_unique_short_identifier_binds() -> None:
    nodes = [_node("n1", "redirect", "src/helpers.py"), _node("n2", "url_for", "src/helpers.py")]

    assert _bound(nodes, _decision("`redirect` returns 303 by default instead of 302")) == {
        "redirect"
    }


def test_ambiguous_short_identifier_does_not_bind() -> None:
    """`send` exists in two files, so it is too generic to identify code."""
    nodes = [_node("n1", "send", "src/one.py"), _node("n2", "send", "src/two.py")]

    assert _bound(nodes, _decision("`send` now flushes because the buffer was dropped")) == set()


def test_distinctive_snake_case_still_binds_when_shared() -> None:
    nodes = [
        _node("n1", "request_context", "src/one.py"),
        _node("n2", "request_context", "src/two.py"),
    ]

    assert _bound(nodes, _decision("`request_context` merged with the app context")) == {
        "request_context"
    }


def test_dotted_identifier_uses_its_last_segment() -> None:
    nodes = [_node("n1", "route", "src/app.py"), _node("n2", "run", "src/app.py")]

    assert _bound(nodes, _decision("`app.route` can be used without parentheses")) == {"route"}


def test_identifier_absent_from_the_graph_does_not_bind() -> None:
    nodes = [_node("n1", "route", "src/app.py")]

    assert _bound(nodes, _decision("`nonexistent_helper` was removed")) == set()
