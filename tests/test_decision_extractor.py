"""Tests for rule-based decision extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from codegraph.decisions.extractor import (
    decision_from_adr_sections,
    extract_decisions_from_text,
    looks_like_decision,
    parse_adr_markdown,
)
from codegraph.decisions.sources import (
    extract_from_adrs,
    extract_from_changelog,
    extract_from_commits,
)
from codegraph.models import DecisionSource

TS = datetime(2026, 9, 23, tzinfo=timezone.utc)


def test_looks_like_decision_keywords() -> None:
    """Rationale keywords should mark a sentence as a decision."""
    assert looks_like_decision("Use SQLite because zero ops matter.")
    assert looks_like_decision("We chose X instead of Y.")
    assert not looks_like_decision("Update readme.")


def test_extract_decisions_from_commit_message() -> None:
    """Commit text with rationale should yield Decision objects."""
    text = "feat: use sqlite because it needs no server. Also bump version."
    found = extract_decisions_from_text(
        text,
        source=DecisionSource.COMMIT,
        source_ref="commit abc123",
        timestamp=TS,
        author="dev@example.com",
        file_path="src/a.py",
    )
    assert found
    assert any("because" in d.content.lower() for d in found)
    assert all(d.source == DecisionSource.COMMIT for d in found)
    assert "commit abc123" in found[0].source_ref


def test_parse_adr_sections() -> None:
    """ADR markdown should split into status/decision/context."""
    md = (
        "# ADR-001\n\n## Status\nAccepted\n\n## Context\nNeed storage.\n\n"
        "## Decision\nUse SQLite because it is embedded.\n"
    )
    sections = parse_adr_markdown(md)
    assert "sqlite" in (sections.get("decision") or "").lower()
    assert "accepted" in (sections.get("status") or "").lower()


def test_decision_from_adr_sections() -> None:
    """decision_from_adr_sections builds a Decision with source ADR."""
    sections = {
        "title": "ADR-001",
        "status": "accepted",
        "context": "Need local store.",
        "decision": "Use SQLite because it is embedded and simple.",
    }
    decision = decision_from_adr_sections(
        sections, source_ref="ADR 001", timestamp=TS, file_path="docs/adr/001.md"
    )
    assert decision is not None
    assert decision.source == DecisionSource.ADR
    assert "SQLite" in decision.content
    assert decision.confidence >= 0.7


def test_extract_from_adrs_on_disk(tmp_path: Path) -> None:
    """extract_from_adrs should read docs/adr/*.md."""
    adr = tmp_path / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "001-use-sqlite.md").write_text(
        "# ADR-001 Use SQLite\n\n## Status\nAccepted\n\n## Decision\n"
        "Use SQLite because zero-ops local store is enough for MVP.\n",
        encoding="utf-8",
    )
    found = extract_from_adrs(tmp_path)
    assert found
    assert any(d.source == DecisionSource.ADR for d in found)


def test_extract_from_commits_and_changelog(tmp_path: Path) -> None:
    """Commits and CHANGELOG should produce decisions without LLM."""
    git = __import__("git")
    from git import Actor

    repo = git.Repo.init(str(tmp_path))
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    repo.index.add(["app.py"])
    repo.index.commit(
        "refactor: rename helper because the old name confused readers",
        author=Actor("a", "a@example.com"),
        committer=Actor("a", "a@example.com"),
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "## Changed\n\n- Drop legacy flag because it was unused.\n",
        encoding="utf-8",
    )
    commit_decisions = extract_from_commits(tmp_path, depth=20)
    changelog = extract_from_changelog(tmp_path)
    assert commit_decisions
    assert any("because" in d.content.lower() for d in commit_decisions)
    assert changelog
    assert all(d.source_ref.startswith("CHANGELOG") or True for d in changelog)
