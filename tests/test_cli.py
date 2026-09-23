"""CodeGraph CLI tests: help, why, index, graph paths."""

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
    assert "决策摘要" in result.stdout
    assert "会话令牌" in result.stdout
    assert "替代方案" in result.stdout
    assert "可信度" in result.stdout


def test_why_bad_format_friendly_error() -> None:
    """Invalid location should fail with a friendly message."""
    result = runner.invoke(app, ["why", "badformat"])
    assert result.exit_code == 2
    assert "参数错误" in result.stdout
    assert "src/auth/session.ts:42" in result.stdout


def test_why_unknown_location_not_found() -> None:
    """Valid but unbound location should report missing decisions."""
    result = runner.invoke(app, ["why", "src/unknown/file.ts:1"])
    assert result.exit_code == 1
    assert "未找到足够决策记录" in result.stdout


def test_index_writes_sqlite_with_nodes(tmp_path: Path) -> None:
    """index should parse a temp .py file and persist SQLite nodes."""
    sample = tmp_path / "hello.py"
    sample.write_text("def greet():\n    return 1\n", encoding="utf-8")
    result = runner.invoke(app, ["index", str(tmp_path)])
    assert result.exit_code == 0
    assert "正在索引" in result.stdout
    assert "索引完成" in result.stdout
    assert "节点数" in result.stdout

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
    assert "代码图快照" in ok.stdout
    assert "变更摘要" in ok.stdout

    bad = runner.invoke(app, ["graph", "--at", "not-a-date", "--scope", "src"])
    assert bad.exit_code == 2
    assert "日期" in bad.stdout
