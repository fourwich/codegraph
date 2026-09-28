"""Conflict detection tests (stateful vs stateless)."""

from __future__ import annotations

from datetime import datetime, timezone

from codegraph.commands.conflicts import find_conflicts, reasons_conflict
from codegraph.models import Decision, DecisionSource, DecisionStatus


def _d(uid: str, content: str, reason: str = "", path: str = "docs/adr/a.md") -> Decision:
    return Decision(
        uid=uid,
        content=content,
        reason=reason,
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ADR,
        source_ref=uid,
        timestamp=datetime(2026, 9, 23, tzinfo=timezone.utc),
        file_path=path,
    )


def test_stateful_vs_stateless_conflict() -> None:
    a = _d("d4", "Use stateful JWT sessions with a server-side denylist.", path="docs/adr/004.md")
    b = _d(
        "d5",
        "Always use stateless JWT and never store session state on the server.",
        path="docs/adr/005.md",
    )
    reason = reasons_conflict(a, b)
    assert reason is not None
    assert "stateful" in reason and "stateless" in reason


def test_find_conflicts_cross_file() -> None:
    a = _d("d4", "Use stateful JWT sessions.", path="docs/adr/004.md")
    b = _d("d5", "Always use stateless JWT.", path="docs/adr/005.md")
    pairs = find_conflicts([a, b], "docs/adr")
    assert pairs and pairs[0][2]


def test_no_false_positive_unrelated() -> None:
    a = _d("d1", "Use SQLite as default backend.", path="docs/adr/001.md")
    b = _d("d2", "Parse sources with tree-sitter.", path="docs/adr/002.md")
    assert reasons_conflict(a, b) is None
