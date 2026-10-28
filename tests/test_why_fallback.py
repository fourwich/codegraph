"""Tests for why decision fallback and content/reason split."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.decisions.extractor import split_content_reason
from codegraph.models import (
    CodeNode,
    Decision,
    DecisionSource,
    DecisionStatus,
    DecisionTier,
)
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    insert_decisions,
    insert_nodes,
)

runner = CliRunner()


def test_split_content_reason() -> None:
    """because/since clauses become reason, not duplicated content."""
    content, reason = split_content_reason(
        "Use SQLite because it is embedded and needs no server"
    )
    assert content == "Use SQLite"
    assert "because" in reason
    assert content != reason


def test_why_file_level_fallback(tmp_path: Path, monkeypatch) -> None:
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

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["why", "src/codegraph/cli.py:24"])

    assert result.exit_code == 0
    assert "Use Typer for the CLI" in result.output
    assert "file-level decision" in result.output

    from codegraph.commands.why import load_decisions_sqlite

    rows, level = load_decisions_sqlite(
        "src/codegraph/cli.py", 24, root=tmp_path, commit_sha=""
    )
    assert level == "file"
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
    assert level == "dir"
    assert len(rows) == 5


def _seed_governed_file(tmp_path: Path) -> None:
    """A file whose only decision governs it from an ADR, with a node elsewhere."""
    sample = tmp_path / "src" / "app.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(
        '"""Module docstring."""\n\n\ndef run():\n    return 1\n', encoding="utf-8"
    )
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_nodes(
            conn,
            [
                CodeNode(
                    uid="n-run",
                    kind="function",
                    name="run",
                    file_path="src/app.py",
                    line_start=4,
                    line_end=5,
                    language="python",
                )
            ],
        )
        insert_decisions(
            conn,
            [
                Decision(
                    uid="d-adr",
                    content="Parse sources with tree-sitter",
                    reason="Because a real AST beats regular expressions",
                    alternatives=["regex"],
                    status=DecisionStatus.ACCEPTED,
                    source=DecisionSource.ADR,
                    source_ref="ADR 002-use-tree-sitter",
                    timestamp=__import__("datetime").datetime(2026, 1, 1),
                    file_path="docs/adr/002-use-tree-sitter.md",
                    tier=DecisionTier.DECISION,
                )
            ],
        )
        insert_decision_links(conn, [("d-adr", "n-run", "src/app.py", 4)])
    finally:
        conn.close()


def test_why_reports_a_decision_that_governs_the_whole_file(
    tmp_path: Path, monkeypatch
) -> None:
    """A line no node covers still reports the decision that governs the file."""
    _seed_governed_file(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["why", "src/app.py:1"])

    assert result.exit_code == 1
    assert "governed by" in result.output
    assert "Parse sources with tree-sitter" in result.output
    assert "ADR 002-use-tree-sitter" in result.output


def test_why_json_exposes_the_governing_decisions(tmp_path: Path, monkeypatch) -> None:
    """Machine consumers get the same fallback in the JSON contract."""
    _seed_governed_file(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["why", "src/app.py:1", "--json"])

    import json

    payload = json.loads(result.output)
    assert payload["decisions"] == []
    assert [d["content"] for d in payload["related"]] == ["Parse sources with tree-sitter"]


def test_why_does_not_add_related_when_a_line_answer_exists(
    tmp_path: Path, monkeypatch
) -> None:
    """The fallback must not decorate a real line-level answer."""
    _seed_governed_file(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["why", "src/app.py:4", "--json"])

    import json

    payload = json.loads(result.output)
    assert [d["uid"] for d in payload["decisions"]] == ["d-adr"]
    assert payload["related"] == []
