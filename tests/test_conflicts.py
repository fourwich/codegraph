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


def test_detect_supersede_conflicts() -> None:
    a = _d("a", "Use offset pagination.")
    b = _d("b", "Supersedes Use offset pagination because deep pages were slow.")
    # b claims supersede but a still accepted
    hits = detect_supersede_conflicts([a, b])
    assert hits and hits[0].type == "supersede"


def test_detect_temporal_conflicts() -> None:
    a = _d("a", "Enable strict TypeScript checks.", ts=TS)
    b = _d("b", "Use lazy loading for all modules.", ts=TS + timedelta(days=2))
    hits = detect_temporal_conflicts([a, b])
    assert hits and hits[0].type == "temporal"


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
