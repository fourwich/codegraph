"""codegraph graph：查看指定时刻的代码图摘要。"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.data import SAMPLE_DECISIONS, SAMPLE_NODES
from codegraph.models import CodeNode, Decision

console = Console()


class DateError(ValueError):
    """日期格式不合法。"""


def parse_date(raw: str) -> date:
    """解析 YYYY-MM-DD 日期字符串。"""
    value = raw.strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DateError(f"日期「{raw}」格式不正确，请使用 YYYY-MM-DD，例如 2024-11-02") from exc


def filter_nodes_by_scope(nodes: list[CodeNode], scope: str) -> list[CodeNode]:
    """按路径前缀过滤节点。"""
    prefix = scope.strip().replace("\\", "/").rstrip("/")
    if not prefix or prefix == ".":
        return list(nodes)
    return [n for n in nodes if n.file_path.startswith(prefix)]


def filter_decisions_at(decisions: list[Decision], at: date) -> list[Decision]:
    """筛选在指定日期（含）之前已产生的决策。"""
    return [d for d in decisions if d.timestamp.date() <= at]


def summarize_changes(at: date, nodes: list[CodeNode], decisions: list[Decision]) -> list[str]:
    """生成指定时刻附近的变更摘要（假数据规则）。"""
    lines: list[str] = []
    for node in nodes[:3]:
        lines.append(f"结构：{node.kind} {node.name} @ {node.file_path}:{node.line_start}")
    for decision in decisions:
        if decision.timestamp.date() == at:
            lines.append(f"决策：{decision.content}（{decision.source_ref}）")
    if not lines:
        lines.append(f"{at.isoformat()} 时刻无额外变更记录，返回基线图")
    return lines


def build_graph_table(
    at: date,
    scope: str,
    nodes: list[CodeNode],
    decisions: list[Decision],
    edge_count: int,
) -> Table:
    """构造代码图摘要表。"""
    table = Table(title=f"代码图快照 · --at {at.isoformat()} · --scope {scope}", show_lines=False)
    table.add_column("指标", style="cyan", no_wrap=True)
    table.add_column("值", style="white")
    table.add_column("说明", style="dim")
    table.add_row("时刻", at.isoformat(), "valid_to 为空表示当前仍有效")
    table.add_row("节点数", str(len(nodes)), "CodeNode")
    table.add_row("边数", str(edge_count), "uses / defined_by / decided_by 模拟")
    table.add_row("决策数", str(len(decisions)), "Decision（不晚于该时刻）")
    return table


def graph_command(
    at: str = typer.Option(..., "--at", help="查询时刻，格式 YYYY-MM-DD", metavar="DATE"),
    scope: str = typer.Option(".", "--scope", help="路径范围，如 src 或 src/auth", metavar="PATH"),
) -> None:
    """输出指定时刻、指定范围的代码图摘要。

    Args:
        at: 历史时刻（YYYY-MM-DD）。
        scope: 路径前缀范围。
    """
    try:
        at_date = parse_date(at)
    except DateError as exc:
        console.print(f"[bold red]参数错误[/] {exc}")
        raise typer.Exit(code=2) from exc

    nodes = filter_nodes_by_scope(SAMPLE_NODES, scope)
    decisions = filter_decisions_at(SAMPLE_DECISIONS, at_date)
    edge_count = len(nodes) * 2 + len(decisions)

    console.print(build_graph_table(at_date, scope, nodes, decisions, edge_count))
    console.print()
    console.print("[bold cyan]变更摘要[/]")
    for line in summarize_changes(at_date, nodes, decisions):
        console.print(f"  · {line}")


app = typer.Typer(help="查询历史时刻的代码图")

if __name__ == "__main__":
    app()
