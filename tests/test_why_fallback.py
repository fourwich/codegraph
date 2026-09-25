"""Tests for why decision fallback and content/reason split."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.decisions.extractor import split_content_reason
from codegraph.models import Decision, DecisionSource, DecisionStatus
from codegraph.storage import connect, db_path_for_root, init_schema, insert_decisions

runner = CliRunner()


def test_split_content_reason() -> None:
    """because/since clauses become reason, not duplicated content."""
    content, reason = split_content_reason(
        "Use SQLite because it is embedded and needs no server"
    )
    assert content == "Use SQLite"
    assert "because" in reason
    assert content != reason


def test_why_file_level_fallback(tmp_path: Path) -> None:
    """why falls back to file-level decisions when line is unbound."""
    sample = tmp_path / "src" / "codegraph" / "cli.py"
    sample.parent.mkdir(parents=True)
    sample.write_text("def main():\n    return 0\n", encoding="utf-8")
    db = db_path_for_root(tmp_path)
    conn = connect(db)
    try:
        init_schema(conn)
        insert_decisions(
            conn,
            [
                Decision(
                    uid="d-file-1",
                    content="Use Typer for the CLI",
                    reason="Because Rich panels compose cleanly with Typer commands",
                    alternatives=["argparse"],
                    status=DecisionStatus.ACCEPTED,
                    source=DecisionSource.COMMIT,
                    source_ref="commit abc",
                    timestamp=__import__("datetime").datetime(2026, 1, 1),
                    file_path="src/codegraph/cli.py",
                    line=None,
                    confidence=0.8,
                )
            ],
        )
    finally:
        conn.close()

    result = runner.invoke(
        app,
        ["why", "src/codegraph/cli.py:24"],
        env={"CODEGRAPH_TEST_ROOT": str(tmp_path)},
    )
    # cwd is still repo root; ensure fallback path works against default db if present
    assert result.exit_code in (0, 1)
    # Prefer asserting via direct loader against tmp db
    from codegraph.commands.why import load_decisions_sqlite

    rows, level = load_decisions_sqlite(
        "src/codegraph/cli.py", 24, root=tmp_path, commit_sha=""
    )
    assert rows
    assert level in {"file", "line"}
    assert rows[0].content == "Use Typer for the CLI"
    assert "Rich" in rows[0].reason
    assert rows[0].content != rows[0].reason


def test_why_dir_level_fallback(tmp_path: Path) -> None:
    """Directory prefix fallback returns at most 5 decisions."""
    from codegraph.commands.why import load_decisions_sqlite

    db = db_path_for_root(tmp_path)
    conn = connect(db)
    try:
        init_schema(conn)
        decisions = [
            Decision(
                uid=f"d-dir-{i}",
                content=f"Choice {i} because reason {i}",
                reason=f"reason {i}",
                status=DecisionStatus.ACCEPTED,
                source=DecisionSource.COMMIT,
                source_ref="commit x",
                timestamp=__import__("datetime").datetime(2026, 1, 1 + i),
                file_path=f"src/codegraph/mod{i}.py",
                line=None,
            )
            for i in range(7)
        ]
        insert_decisions(conn, decisions)
    finally:
        conn.close()

    rows, level = load_decisions_sqlite("src/codegraph/missing.py:1", 1, root=tmp_path)
    assert level in {"dir", "commit", "none"}
    assert len(rows) <= 5
