"""codegraph index：用 tree-sitter 解析源码并写入 SQLite 图。"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from codegraph.models import CodeNode, Edge, normalize_location_path
from codegraph.parser.base import BaseParser
from codegraph.parser.registry import get_parser_for_path, is_supported_source
from codegraph.storage import (
    clear_graph,
    connect,
    count_edges,
    count_nodes,
    db_path_for_root,
    init_schema,
    insert_edges,
    insert_nodes,
)

console = Console()
logger = logging.getLogger(__name__)

# 索引时跳过的目录
SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".codegraph",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

INDEX_STEPS: list[str] = [
    "遍历源码文件",
    "tree-sitter 解析 AST",
    "抽取 contains / uses 边",
    "写入 SQLite 图",
]


def resolve_repo_path(path: Path) -> Path:
    """解析并校验仓库路径。"""
    target = path.expanduser().resolve()
    if not target.exists():
        raise typer.BadParameter(f"路径不存在：{path}")
    return target


def iter_source_files(root: Path) -> list[Path]:
    """递归收集受支持的源文件，跳过无关目录。"""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if is_supported_source(path):
            files.append(path)
    return files


def parse_all_files(root: Path, files: list[Path]) -> tuple[list[CodeNode], list[Edge]]:
    """解析全部文件，汇总节点与边；单文件失败仅警告。"""
    nodes: list[CodeNode] = []
    edges: list[Edge] = []
    parsers: list[BaseParser] = []

    for file_path in files:
        parser = get_parser_for_path(file_path)
        if parser is None:
            continue
        try:
            file_nodes = parser.parse_file(file_path)
        except Exception as exc:  # noqa: BLE001 — 单文件失败不中断整体索引
            logger.warning("解析失败，跳过 %s: %s", file_path, exc)
            console.print(f"[yellow]warn[/] 解析失败，跳过 {normalize_location_path(str(file_path))}: {exc}")
            continue
        nodes.extend(file_nodes)
        parsers.append(parser)

    for parser in parsers:
        edges.extend(parser.extract_edges(nodes))
    return nodes, edges


def run_index_progress(steps: list[str]) -> None:
    """用 Rich 进度条展示索引阶段。"""
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
            task = progress.add_task(step, total=8)
            for _ in range(8):
                progress.update(task, advance=1)
            progress.update(overall, advance=1)


def write_graph(db_path: Path, nodes: list[CodeNode], edges: list[Edge]) -> tuple[int, int]:
    """写入 SQLite 并返回 (节点数, 边数)。"""
    conn = connect(db_path)
    try:
        init_schema(conn)
        clear_graph(conn)
        insert_nodes(conn, nodes)
        insert_edges(conn, edges)
        return count_nodes(conn), count_edges(conn)
    finally:
        conn.close()


def index_command(
    path: Path = typer.Argument(..., help="要索引的仓库或目录路径", metavar="PATH"),
) -> None:
    """解析代码结构并写入本地 SQLite 图（.codegraph/graph.db）。

    Args:
        path: 仓库根目录或子目录。
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    try:
        target = resolve_repo_path(path)
    except typer.BadParameter as exc:
        console.print(f"[bold red]参数错误[/] {exc}")
        raise typer.Exit(code=2) from exc

    root = target if target.is_dir() else target.parent
    console.print(f"[bold cyan]正在索引[/] {target} ...")

    files = iter_source_files(root)
    run_index_progress(INDEX_STEPS)
    nodes, edges = parse_all_files(root, files)
    db_path = db_path_for_root(root)
    node_count, edge_count = write_graph(db_path, nodes, edges)

    console.print()
    console.print(f"[bold green]索引完成[/]  [bold]{root}[/]")
    console.print(f"  · 文件数：[bold]{len(files)}[/]")
    console.print(f"  · 节点数：[bold]{node_count}[/]")
    console.print(f"  · 边数：[bold]{edge_count}[/]")
    console.print(f"  · 数据库：[bold]{db_path}[/]")
    console.print("[dim]下一步：codegraph why <file>:<line>  查看决策卡片[/]")


app = typer.Typer(help="索引代码库（tree-sitter + SQLite）")

if __name__ == "__main__":
    app()
