"""CodeGraph CLI 测试：覆盖 help、why、index、graph 主路径。"""

from __future__ import annotations

from typer.testing import CliRunner

from codegraph.cli import app

runner = CliRunner()


def test_help_lists_core_commands() -> None:
    """--help 应展示核心命令说明。"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.stdout
    assert "why" in result.stdout
    assert "graph" in result.stdout
    assert "decisions" in result.stdout
    # Typer 默认开启 shell completion，help 中通常会出现 completion
    assert "命令" in result.stdout or "Commands" in result.stdout


def test_why_known_location_shows_decision_card() -> None:
    """已知 file:line 应输出决策卡片字段。"""
    result = runner.invoke(app, ["why", "src/auth/session.ts:42"])
    assert result.exit_code == 0
    assert "决策摘要" in result.stdout
    assert "会话令牌" in result.stdout
    assert "替代方案" in result.stdout
    assert "可信度" in result.stdout


def test_why_bad_format_friendly_error() -> None:
    """非法位置应友好报错并返回退出码 2。"""
    result = runner.invoke(app, ["why", "badformat"])
    assert result.exit_code == 2
    assert "参数错误" in result.stdout
    assert "src/auth/session.ts:42" in result.stdout


def test_why_unknown_location_not_found() -> None:
    """合法但无决策的位置应提示未找到。"""
    result = runner.invoke(app, ["why", "src/unknown/file.ts:1"])
    assert result.exit_code == 1
    assert "未找到足够决策记录" in result.stdout


def test_index_shows_progress_and_stats(tmp_path) -> None:
    """index 应输出统计信息。"""
    result = runner.invoke(app, ["index", str(tmp_path)])
    assert result.exit_code == 0
    assert "正在索引" in result.stdout
    assert "索引完成" in result.stdout
    assert "节点数" in result.stdout
    assert "边数" in result.stdout


def test_graph_table_and_date_validation(tmp_path) -> None:
    """graph 正常路径与非法日期路径。"""
    ok = runner.invoke(app, ["graph", "--at", "2024-11-02", "--scope", "src"])
    assert ok.exit_code == 0
    assert "代码图快照" in ok.stdout
    assert "变更摘要" in ok.stdout

    bad = runner.invoke(app, ["graph", "--at", "not-a-date", "--scope", "src"])
    assert bad.exit_code == 2
    assert "日期" in bad.stdout
