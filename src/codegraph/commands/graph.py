"""codegraph graph：查看指定时刻的代码图摘要。"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.models import SAMPLE_DECISIONS, Decision
from codegraph.storage import connect, count_edges, count_nodes, db_path_for_root

console = Console()


class DateError(ValueError):
    """Date string is invalid."""


def parse_date(raw: str) -> date:
    """Parse YYYY-MM-DD date string."""
    value = raw.strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DateError(
            f"日期「{raw}」格式不正确，请使用 YYYY-MM-DD，例如 2024-11-02"
        ) from exc


def filter_decisions_at(decisions: list[Decision], at: date) -> list[Decision]:
    """Return decisions created on or before the given date."""
    return [d for d in decisions if d.timestamp.date() <= at]


def load_sqlite_stats(root: Path | None = None) -> tuple[int, int] | None:
    """Load (node_count, edge_count) from SQLite if index exists."""
    db_path = db_path_for_root(root or Path.cwd())
    if not db_path.exists():
        return None
    conn = connect(db_path)
    try:
        return count_nodes(conn), count_edges(conn)
    finally:
        conn.close()


def summarize_changes(at: date, decisions: list[Decision]) -> list[str]:
    """Build a short change summary for the snapshot date."""
    lines: list[str] = []
    for decision in decisions:
        if decision.timestamp.date() == at:
            lines.append(f"决策：{decision.content}（{decision.source_ref}）")
    if not lines:
        lines.append(f"{at.isoformat()} 时刻无额外变更记录，返回基线图")
    return lines


def build_graph_table(
    at: date,
    scope: str,
    node_count: int,
    edge_count: int,
    decisions: list[Decision],
) -> Table:
    """Build the code-graph summary table."""
    table = Table(
        title=f"代码图快照 · --at {at.isoformat()} · --scope {scope}",
        show_lines=False,
    )
    table.add_column("指标", style="cyan", no_wrap=True)
    table.add_column("值", style="white")
    table.add_column("说明", style="dim")
    table.add_row("时刻", at.isoformat(), "valid_to 为空表示当前仍有效")
    table.add_row("节点数", str(node_count), "CodeNode")
    table.add_row("边数", str(edge_count), "uses / defined_by / contains")
    table.add_row("决策数", str(len(decisions)), "Decision（不晚于该时刻）")
    return table


def graph_command(
    at: str = typer.Option(..., "--at", help="查询时刻，格式 YYYY-MM-DD", metavar="DATE"),
    scope: str = typer.Option(
        ".", "--scope", help="路径范围，如 src 或 src/auth", metavar="PATH"
    ),
) -> None:
    """Print a code-graph snapshot for a historical date and scope.

    Args:
        at: Snapshot date (YYYY-MM-DD).
        scope: Path prefix scope.
    """
    try:
        at_date = parse_date(at)
    except DateError as exc:
        console.print(f"[bold red]参数错误[/] {exc}")
        raise typer.Exit(code=2) from exc

    decisions = filter_decisions_at(SAMPLE_DECISIONS, at_date)
    stats = load_sqlite_stats()
    node_count, edge_count = stats if stats else (0, 0)

    console.print(build_graph_table(at_date, scope, node_count, edge_count, decisions))
    console.print()
    console.print("[bold cyan]变更摘要[/]")
    for line in summarize_changes(at_date, decisions):
        console.print(f"  · {line}")


app = typer.Typer(help="查询历史时刻的代码图")

if __name__ == "__main__":
    app()
