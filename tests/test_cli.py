"""CodeGraph CLI tests: help, why, index, graph, and Dgraph flags."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.storage import count_nodes, db_path_for_root

runner = CliRunner()


def test_help_lists_four_commands() -> None:
    """--help should list four commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.stdout
    assert "why" in result.stdout
    assert "graph" in result.stdout
    assert "decisions" in result.stdout


def test_why_known_location_shows_decision_card() -> None:
    """Known file:line should render decision card fields."""
    result = runner.invoke(app, ["why", "src/auth/session.ts:42"])
    assert result.exit_code == 0
    assert "[Decision]" in result.stdout
    assert "stateful JWT" in result.stdout
    assert "[Alternatives]" in result.stdout
    assert "[Confidence]" in result.stdout


def test_why_bad_format_friendly_error() -> None:
    """Invalid location should fail with a friendly message."""
    result = runner.invoke(app, ["why", "badformat"])
    assert result.exit_code == 2
    assert "Invalid argument" in result.stdout
    assert "src/auth/session.ts:42" in result.stdout


def test_why_unknown_location_not_found() -> None:
    """Valid but unbound location should report missing decisions."""
    result = runner.invoke(app, ["why", "src/unknown/file.ts:1"])
    assert result.exit_code == 1
    assert "No decision record found" in result.stdout


def test_index_writes_sqlite_with_nodes(tmp_path: Path) -> None:
    """index should parse a temp .py file and persist SQLite nodes."""
    sample = tmp_path / "hello.py"
    sample.write_text("def greet():\n    return 1\n", encoding="utf-8")
    result = runner.invoke(app, ["index", str(tmp_path)])
    assert result.exit_code == 0
    assert "Indexing" in result.stdout
    assert "Index complete" in result.stdout
    assert "Nodes" in result.stdout

    db_path = db_path_for_root(tmp_path.resolve())
    assert db_path.exists()
    conn = sqlite3.connect(str(db_path))
    try:
        assert count_nodes(conn) > 0
    finally:
        conn.close()


def test_graph_table_and_date_validation() -> None:
    """graph happy path and invalid date path."""
    ok = runner.invoke(app, ["graph", "--at", "2024-11-02", "--scope", "src"])
    assert ok.exit_code == 0
    assert "Code graph snapshot" in ok.stdout
    assert "Change summary" in ok.stdout

    bad = runner.invoke(app, ["graph", "--at", "not-a-date", "--scope", "src"])
    assert bad.exit_code == 2
    assert "Date" in bad.stdout


def test_index_dgraph_backend_connection_failure(tmp_path: Path) -> None:
    """index --backend dgraph should exit 3 when Dgraph is unreachable."""
    sample = tmp_path / "hello.py"
    sample.write_text("def greet():\n    return 1\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["index", str(tmp_path), "--backend", "dgraph"],
        env={"DGRAPH_ALPHA": "localhost:59999"},
    )
    assert result.exit_code == 3
    assert "Dgraph connection failed" in result.stdout


def test_why_dgraph_backend_flag_parsed() -> None:
    """why should accept --backend dgraph and still parse location args."""
    result = runner.invoke(
        app,
        ["why", "badformat", "--backend", "dgraph"],
        env={"DGRAPH_ALPHA": "localhost:59999"},
    )
    assert result.exit_code == 2
    assert "Invalid argument" in result.stdout


def test_graph_dgraph_backend_connection_failure() -> None:
    """graph --backend dgraph should exit 3 when Dgraph is down."""
    result = runner.invoke(
        app,
        ["graph", "--at", "2026-09-23", "--scope", "src", "--backend", "dgraph"],
        env={"DGRAPH_ALPHA": "localhost:59999"},
    )
    assert result.exit_code == 3
    assert "Dgraph connection failed" in result.stdout


def test_conflicts_dgraph_backend_connection_failure() -> None:
    """conflicts --backend dgraph should exit 3 when Dgraph is down."""
    result = runner.invoke(
        app,
        ["conflicts", "--scope", "src", "--backend", "dgraph"],
        env={"DGRAPH_ALPHA": "localhost:59999"},
    )
    assert result.exit_code == 3
    assert "Dgraph connection failed" in result.stdout


def test_export_for_ai_writes_pack(tmp_path: Path) -> None:
    """export --for-ai should write a context markdown pack."""
    out = tmp_path / "context.md"
    result = runner.invoke(
        app,
        ["export", "--for-ai", "--scope", "src", "--output", str(out)],
    )
    assert result.exit_code == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "CodeGraph Context Pack" in text
    assert "Paste this into your coding assistant" in text


def test_export_requires_for_ai() -> None:
    """export without --for-ai should fail with invalid argument."""
    result = runner.invoke(app, ["export", "--scope", "src"])
    assert result.exit_code == 2
    assert "Invalid argument" in result.stdout
