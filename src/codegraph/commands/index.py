"""codegraph index：索引仓库并写入图（MVP 用假数据模拟）。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from codegraph.data import SAMPLE_DECISIONS, SAMPLE_NODES

console = Console()

# 模拟索引阶段：顺序展示给用户看
INDEX_STEPS: list[str] = [
    "扫描源码文件",
    "tree-sitter 解析 AST（模拟）",
    "抽取 uses / defined_by 边",
    "遍历 Git 历史（模拟）",
    "关联 PR / Issue / ADR 决策",
    "写入 Dgraph（模拟）",
]


def resolve_repo_path(path: Path) -> Path:
    """解析并校验仓库路径。"""
    target = path.expanduser().resolve()
    if not target.exists():
        raise typer.BadParameter(f"路径不存在：{path}")
    return target


def count_fake_graph_stats() -> tuple[int, int]:
    """返回模拟图统计：节点数与边数。"""
    node_count = len(SAMPLE_NODES)
    # 边：每个决策到代码 uses + 依赖链，用简单规则模拟
    edge_count = len(SAMPLE_NODES) * 2 + len(SAMPLE_DECISIONS)
    return node_count, edge_count


def run_index_progress(steps: list[str]) -> None:
    """用 Rich 进度条模拟多阶段索引。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall = progress.add_task("索引进度", total=len(steps))
        for step in steps:
            task = progress.add_task(step, total=10)
            for _ in range(10):
                progress.update(task, advance=1)
            progress.update(overall, advance=1)


def index_command(
    path: Path = typer.Argument(..., help="要索引的仓库或目录路径", metavar="PATH"),
) -> None:
    """解析代码 + 摄取 Git 历史 + 写入图数据库（当前为模拟流程）。

    Args:
        path: 仓库根目录或子目录。
    """
    try:
        target = resolve_repo_path(path)
    except typer.BadParameter as exc:
        console.print(f"[bold red]参数错误[/] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(f"[bold cyan]正在索引[/] {target} ...")
    if target.is_file():
        console.print("[dim]提示：当前指向文件；生产环境会向上查找仓库根。[/]")

    run_index_progress(INDEX_STEPS)
    node_count, edge_count = count_fake_graph_stats()

    console.print()
    console.print(f"[bold green]索引完成[/]  [bold]{target}[/]")
    console.print(f"  · 节点数：[bold]{node_count}[/]")
    console.print(f"  · 边数：[bold]{edge_count}[/]")
    console.print(f"  · 决策数：[bold]{len(SAMPLE_DECISIONS)}[/]")
    console.print("[dim]下一步：codegraph why <file>:<line>  查看决策卡片[/]")


app = typer.Typer(help="索引代码库（MVP 模拟）")

if __name__ == "__main__":
    app()
