"""codegraph decisions：查看文件的决策演化链。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.data import SAMPLE_DECISIONS, normalize_location_path

console = Console()


def filter_by_file(file_path: str) -> list:
    """返回绑定到指定文件的决策，按时间排序。"""
    prefix = normalize_location_path(file_path)
    matched = [d for d in SAMPLE_DECISIONS if d.file_path == prefix or d.file_path.startswith(prefix)]
    return sorted(matched, key=lambda d: d.timestamp)


def decisions_command(
    file: Path = typer.Option(..., "--file", help="文件路径", metavar="PATH"),
    timeline: bool = typer.Option(False, "--timeline", help="按时间顺序展示演化链"),
) -> None:
    """返回决策演化链。

    Args:
        file: 目标文件路径。
        timeline: 是否按时间线输出。
    """
    rows = filter_by_file(str(file))
    if not rows:
        console.print("[bold yellow]未找到足够决策记录[/]")
        raise typer.Exit(code=1)

    table = Table(title=f"决策演化 · {file}")
    table.add_column("时间", style="cyan")
    table.add_column("状态")
    table.add_column("摘要", overflow="fold")
    table.add_column("来源", style="dim")

    ordered = list(reversed(rows)) if timeline else rows
    for decision in ordered:
        table.add_row(
            decision.timestamp.date().isoformat(),
            decision.status.value,
            decision.content,
            decision.source_ref,
        )
    console.print(table)


app = typer.Typer(help="查询文件的决策演化链")

if __name__ == "__main__":
    app()
