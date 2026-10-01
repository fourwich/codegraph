"""Tests for three-layer conflict detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.decisions.conflicts import (
    detect_all,
    detect_supersede_conflicts,
    detect_temporal_conflicts,
    detect_word_opposites,
)
from codegraph.models import Decision, DecisionSource, DecisionStatus

runner = CliRunner()
TS = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _d(uid: str, content: str, reason: str = "", path: str = "docs/adr/x.md",
       status: DecisionStatus = DecisionStatus.ACCEPTED,
       ts: datetime | None = None) -> Decision:
    return Decision(
        uid=uid,
        content=content,
        reason=reason,
        status=status,
        source=DecisionSource.ADR,
        source_ref=uid,
        timestamp=ts or TS,
        file_path=path,
    )


def test_detect_word_opposites_stateful_vs_stateless() -> None:
    a = _d("a", "We use stateful server-side sessions with a Redis store.",
           "Need one-click logout.", path="docs/adr/004.md")
    b = _d("b", "We prefer stateless JWT tokens and avoid server-side session state.",
           "Stateless scales better.", path="docs/adr/005.md")
    # same folder location
    hits = detect_word_opposites([a, b])
    assert hits and hits[0].type == "opposite"
    assert "stateful" in hits[0].matched_words or "stateless" in hits[0].matched_words


def test_word_opposites_need_a_shared_topic() -> None:
    """Unrelated decisions in one folder are not a contradiction."""
    a = _d("a", "Use SQLite as the default backend under .codegraph/graph.db.",
           "Judges must run the CLI without a database server.", path="docs/adr/001.md")
    b = _d("b", "We prefer stateless JWT tokens and avoid server-side session state.",
           "Stateless tokens scale better.", path="docs/adr/005.md")
    assert detect_word_opposites([a, b]) == []


def test_word_matching_uses_boundaries() -> None:
    """`use` must not fire inside `because`, nor `sync` inside `async`."""
    a = _d("a", "Disable the retry loop because it hides failures.", path="src/x.py")
    b = _d("b", "Enable the retry loop for flaky networks.", path="src/x.py")
    hits = detect_word_opposites([a, b])
    assert hits, "the enable/disable pair should still be detected"
    assert set(hits[0].matched_words) == {"enable", "disable"}

    c = _d("c", "Keep the async client as the only transport.", path="src/y.py")
    d = _d("d", "Keep synchronous calls for simplicity.", path="src/y.py")
    assert detect_word_opposites([c, d]) == []


def test_detect_supersede_conflicts() -> None:
    a = _d("a", "Use offset pagination.")
    b = _d("b", "Supersedes Use offset pagination because deep pages were slow.")
    # b claims supersede but a still accepted
    hits = detect_supersede_conflicts([a, b])
    assert hits and hits[0].type == "supersede"


def test_detect_temporal_conflicts() -> None:
    """A short-window reversal with opposite terms is temporal."""
    a = _d("a", "Enable strict TypeScript checks.", ts=TS, path="src/x.ts")
    b = _d("b", "Disable strict TypeScript checks for the legacy folder.",
           ts=TS + timedelta(days=2), path="src/x.ts")
    hits = detect_temporal_conflicts([a, b])
    assert hits and hits[0].type == "temporal"


def test_temporal_ignores_unrelated_neighbours() -> None:
    """Two unrelated decisions close in time are not a conflict."""
    a = _d("a", "Enable strict TypeScript checks.", ts=TS, path="src/x.ts")
    b = _d("b", "Use lazy loading for all modules.", ts=TS + timedelta(days=2),
           path="src/x.ts")
    assert detect_temporal_conflicts([a, b]) == []


def test_detect_all_deduplicates() -> None:
    a = _d("a", "We use stateful sessions.", path="docs/adr/004.md")
    b = _d("b", "We prefer stateless tokens.", path="docs/adr/005.md")
    # same pair can fire opposite + temporal; detect_all keeps one
    hits = detect_all([a, b])
    assert len(hits) == 1


def test_conflicts_command_table_output() -> None:
    result = runner.invoke(app, ["conflicts", "--scope", "docs/adr"])
    assert result.exit_code == 0
    assert "Summary" in result.stdout or "No conflicts" in result.stdout


def test_conflicts_command_json_output() -> None:
    result = runner.invoke(app, ["conflicts", "--scope", "docs/adr", "--format", "json"])
    assert result.exit_code == 0
    assert '"conflicts"' in result.stdout or '"summary"' in result.stdout


def test_conflicts_command_no_conflicts() -> None:
    result = runner.invoke(app, ["conflicts", "--scope", "src/does/not/exist"])
    assert result.exit_code == 0
    assert "No conflicts detected" in result.stdout
