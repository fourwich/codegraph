"""Three-tier extraction: only records with a rationale are decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.decisions.conflicts import detect_all
from codegraph.decisions.extractor import (
    decision_from_commit_subject,
    decisions_from_commit_body,
    is_dependency_commit,
)
from codegraph.models import (
    CodeNode,
    Decision,
    DecisionSource,
    DecisionStatus,
    DecisionTier,
    select_decisions,
)
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decisions,
    insert_nodes,
)

TS = datetime(2026, 9, 24, tzinfo=timezone.utc)
runner = CliRunner()


def _subject(message: str) -> Decision:
    decision = decision_from_commit_subject(
        message, source_ref="commit " + "a" * 40, timestamp=TS
    )
    assert decision is not None
    return decision


def test_plain_commit_subject_is_an_event() -> None:
    """A chore subject carries no rationale, so it is history, not a decision."""
    decision = _subject("chore: use the new logo (#7316)")
    assert decision.tier is DecisionTier.EVENT
    assert decision.confidence == 0.5
    assert decision.reason == ""
    assert decision.alternatives == []


def test_subject_with_rejected_alternative_is_a_decision() -> None:
    """'instead of X' is a recorded alternative, so it becomes a decision."""
    decision = _subject("refactor: use node:buffer instead of safe-buffer (#6071)")
    assert decision.tier is DecisionTier.DECISION
    assert decision.content == "use node:buffer"
    assert decision.alternatives == ["safe-buffer (#6071)"]
    assert decision.confidence == 0.6


def test_dependency_bump_without_reason_is_an_event() -> None:
    """A bare version bump records no rationale."""
    decision = _subject("build(deps): bump morgan from 1.12.0 to 1.12.1 (#7493)")
    assert decision.tier is DecisionTier.EVENT
    assert decision.category == "dependency"


def test_dependency_bump_with_reason_is_a_decision() -> None:
    """A bump that says why (security) is a dependency decision."""
    decision = _subject(
        "deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590 (#7390)"
    )
    assert decision.tier is DecisionTier.DECISION
    assert decision.category == "dependency"
    assert "CVE-2026-12590" in decision.reason
    assert decision.confidence == 0.65


def test_is_dependency_commit_variants() -> None:
    """Both the build(deps) and deps: prefixes count as dependency commits."""
    assert is_dependency_commit("build(deps): bump qs from 6.5.2 to 6.5.3")
    assert is_dependency_commit("deps: bump qs minimum to 6.16.0 (#7478)")
    assert is_dependency_commit("chore(deps-dev): bump morgan to 1.12.1")
    assert not is_dependency_commit("feat: use the new logo (#7316)")


def test_commit_body_bullet_with_because_is_a_decision() -> None:
    """A bullet that states a reason is a decision at higher confidence."""
    message = (
        "refactor: rework the cache\n\n"
        "- Cache keys carry a tenant prefix because cross-tenant reads happened\n"
        "- bump a readme typo\n"
    )
    found = decisions_from_commit_body(message, source_ref="commit b", timestamp=TS)
    assert len(found) == 1
    assert found[0].tier is DecisionTier.DECISION
    assert found[0].confidence == 0.7
    assert "cross-tenant" in found[0].reason


def test_select_decisions_filters_by_default() -> None:
    """Default selection keeps non-dependency decisions only."""
    design = Decision(
        uid="d1", content="keep", status=DecisionStatus.ACCEPTED,
        source=DecisionSource.ADR, source_ref="ADR 1", timestamp=TS,
        reason="because", tier=DecisionTier.DECISION,
    )
    dep = Decision(
        uid="d2", content="bump", status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT, source_ref="commit x", timestamp=TS,
        category="dependency", reason="to fix a CVE", tier=DecisionTier.DECISION,
    )
    event = Decision(
        uid="e1", content="use the new logo", status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT, source_ref="commit y", timestamp=TS,
        tier=DecisionTier.EVENT,
    )

    assert [d.uid for d in select_decisions([design, dep, event])] == ["d1"]
    assert [d.uid for d in select_decisions([design, dep, event], include_dependency=True)] == [
        "d1",
        "d2",
    ]
    assert [d.uid for d in select_decisions([design, dep, event], include_events=True)] == [
        "d1",
        "e1",
    ]


def test_conflicts_ignore_events() -> None:
    """Two contradictory commit subjects must not be reported as a conflict."""
    a = Decision(
        uid="a", content="add the new logo", status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT, source_ref="commit a", timestamp=TS,
        file_path="README.md", tier=DecisionTier.EVENT,
    )
    b = Decision(
        uid="b", content="remove the old logo", status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT, source_ref="commit b", timestamp=TS,
        file_path="README.md", tier=DecisionTier.EVENT,
    )
    assert detect_all(select_decisions([a, b])) == []


def _seed(tmp_path: Path) -> None:
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_nodes(
            conn,
            [
                CodeNode(
                    uid="n1", kind="function", name="f", file_path="src/x.py",
                    line_start=1, line_end=20, language="python",
                )
            ],
        )
        event = Decision(
            uid="ev", content="use the new logo", status=DecisionStatus.ACCEPTED,
            source=DecisionSource.COMMIT, source_ref="commit e", timestamp=TS,
            file_path="src/x.py", tier=DecisionTier.EVENT,
        )
        decision = Decision(
            uid="dec", content="cache the slice because allocation is hot",
            reason="because allocation is hot", status=DecisionStatus.ACCEPTED,
            source=DecisionSource.COMMIT, source_ref="commit d", timestamp=TS,
            file_path="src/x.py", tier=DecisionTier.DECISION,
        )
        insert_decisions(conn, [event, decision])
    finally:
        conn.close()


def test_why_hides_events_unless_requested(tmp_path: Path, monkeypatch) -> None:
    """`why` shows decisions only; --include-events reveals history records."""
    _seed(tmp_path)
    monkeypatch.chdir(tmp_path)

    default = runner.invoke(app, ["why", "src/x.py:5", "--json"])
    assert default.exit_code == 0, default.output
    assert "cache the slice" in default.output
    assert "use the new logo" not in default.output

    with_events = runner.invoke(app, ["why", "src/x.py:5", "--json", "--include-events"])
    assert with_events.exit_code == 0, with_events.output
    assert "use the new logo" in with_events.output


def test_why_reports_hidden_history(tmp_path: Path, monkeypatch) -> None:
    """With nothing but history, `why` says so instead of "no record"."""
    _seed(tmp_path)
    conn = connect(db_path_for_root(tmp_path))
    try:
        conn.execute("DELETE FROM decisions WHERE uid = 'dec'")
        conn.commit()
    finally:
        conn.close()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["why", "src/x.py:5"])
    assert result.exit_code == 1
    assert "--include-events" in result.output


def test_adr_decision_path_is_repo_relative(tmp_path: Path) -> None:
    """ADR records must not store absolute paths."""
    from codegraph.decisions.sources import extract_from_adrs

    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "001-x.md").write_text(
        "# ADR 001\n\n## Status\nAccepted\n\n"
        "## Context\nWe needed X because Y was too slow.\n\n"
        "## Decision\nUse X.\n",
        encoding="utf-8",
    )
    found = extract_from_adrs(tmp_path)
    assert found
    assert found[0].file_path == "docs/adr/001-x.md"
    assert found[0].tier is DecisionTier.DECISION


def test_legacy_rows_without_tier_read_as_decisions(tmp_path: Path) -> None:
    """An older database missing the tier column is migrated on open."""
    from codegraph.storage import query_all_decisions

    db = db_path_for_root(tmp_path)
    conn = connect(db)
    try:
        init_schema(conn)
        conn.execute("ALTER TABLE decisions DROP COLUMN tier")
        conn.execute(
            "INSERT INTO decisions (uid, content, reason, alternatives, status, source, "
            "source_ref, timestamp, author, file_path, line, constraints, confidence, category) "
            "VALUES ('legacy', 'old record', 'because', '[]', 'accepted', 'adr', "
            "'ADR 9', ?, '', '', NULL, '[]', 0.8, 'design')",
            (TS.isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()

    # Reopening runs the migration that re-adds `tier`.
    reopened = connect(db)
    try:
        columns = {row[1] for row in reopened.execute("PRAGMA table_info(decisions)")}
        assert "tier" in columns
        rows = query_all_decisions(reopened)
        assert rows[0].tier is DecisionTier.DECISION
    finally:
        reopened.close()
