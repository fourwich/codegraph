"""codegraph index: parse sources and write to SQLite or Dgraph."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from codegraph.models import SAMPLE_DECISIONS, CodeNode, Edge, normalize_location_path
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

# Directories skipped while walking the tree
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
    "Walk source files",
    "Parse AST with tree-sitter",
    "Extract contains / uses edges",
    "Write graph store",
]


def resolve_repo_path(path: Path) -> Path:
    """Resolve and validate the repository path."""
    target = path.expanduser().resolve()
    if not target.exists():
        raise typer.BadParameter(f"Path not found: {path}")
    return target


def iter_source_files(root: Path) -> list[Path]:
    """Recursively collect supported source files."""
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
    """Parse all files into nodes and edges; skip broken files with a warning."""
    nodes: list[CodeNode] = []
    edges: list[Edge] = []
    parsers: list[BaseParser] = []

    for file_path in files:
        parser = get_parser_for_path(file_path)
        if parser is None:
            continue
        try:
            file_nodes = parser.parse_file(file_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parse failed, skip %s: %s", file_path, exc)
            console.print(
                f"[yellow]warn[/] Parse failed, skipped "
                f"{normalize_location_path(str(file_path))}: {exc}"
            )
            continue
        nodes.extend(file_nodes)
        parsers.append(parser)

    for parser in parsers:
        edges.extend(parser.extract_edges(nodes))
    return nodes, edges


def run_index_progress(steps: list[str]) -> None:
    """Show multi-stage index progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall = progress.add_task("Indexing", total=len(steps))
        for step in steps:
            task = progress.add_task(step, total=8)
            for _ in range(8):
                progress.update(task, advance=1)
            progress.update(overall, advance=1)


def write_sqlite_graph(db_path: Path, nodes: list[CodeNode], edges: list[Edge]) -> tuple[int, int]:
    """Persist nodes/edges to SQLite and return counts."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        clear_graph(conn)
        insert_nodes(conn, nodes)
        insert_edges(conn, edges)
        return count_nodes(conn), count_edges(conn)
    finally:
        conn.close()


def write_dgraph_graph(nodes: list[CodeNode], edges: list[Edge]) -> tuple[int, int, int]:
    """Persist nodes/edges/decisions to Dgraph and return counts."""
    from codegraph.graph import DgraphClient, DgraphConnectionError

    try:
        client = DgraphClient()
    except DgraphConnectionError as exc:
        console.print(f"[bold red]Dgraph connection failed[/] {exc}")
        raise typer.Exit(code=3) from exc

    try:
        if not client.ping():
            console.print(
                "[bold red]Dgraph connection failed[/] Cannot reach alpha. "
                "Run docker compose up -d first."
            )
            raise typer.Exit(code=3)
        client.init_schema()
        for node in nodes:
            client.upsert_node(node)
        for edge in edges:
            client.upsert_edge(edge)
        for decision in SAMPLE_DECISIONS:
            client.upsert_decision(decision)
        return len(nodes), len(edges), len(SAMPLE_DECISIONS)
    except typer.Exit:
        raise
    except DgraphConnectionError as exc:
        console.print(f"[bold red]Dgraph connection failed[/] {exc}")
        raise typer.Exit(code=3) from exc
    finally:
        client.close()


def index_command(
    path: Path = typer.Argument(..., help="Repository or directory path to index", metavar="PATH"),
    backend: str = typer.Option(
        "sqlite",
        "--backend",
        help="Graph backend: sqlite | dgraph",
        metavar="BACKEND",
    ),
) -> None:
    """Parse sources with tree-sitter and persist the code graph.

    Args:
        path: Repository root or subdirectory.
        backend: Storage backend, sqlite (default) or dgraph.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    try:
        target = resolve_repo_path(path)
    except typer.BadParameter as exc:
        console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    if backend not in {"sqlite", "dgraph"}:
        console.print(
            f"[bold red]Invalid argument[/] Unknown backend: {backend} (use sqlite | dgraph)"
        )
        raise typer.Exit(code=2)

    root = target if target.is_dir() else target.parent
    console.print(f"[bold cyan]Indexing[/] {target} ... [dim]backend={backend}[/]")

    files = iter_source_files(root)
    run_index_progress(INDEX_STEPS)
    nodes, edges = parse_all_files(root, files)

    if backend == "dgraph":
        node_count, edge_count, decision_count = write_dgraph_graph(nodes, edges)
        console.print()
        console.print(f"[bold green]Index complete[/]  [bold]{root}[/]  [dim]Dgraph[/]")
        console.print(f"  · Files: [bold]{len(files)}[/]")
        console.print(f"  · Nodes: [bold]{node_count}[/]")
        console.print(f"  · Edges: [bold]{edge_count}[/]")
        console.print(f"  · Decisions: [bold]{decision_count}[/]")
        console.print(
            "  · Dgraph UI: "
            "[link=http://localhost:8080/?latest]http://localhost:8080/?latest[/link]"
        )
    else:
        db_path = db_path_for_root(root)
        node_count, edge_count = write_sqlite_graph(db_path, nodes, edges)
        console.print()
        console.print(f"[bold green]Index complete[/]  [bold]{root}[/]")
        console.print(f"  · Files: [bold]{len(files)}[/]")
        console.print(f"  · Nodes: [bold]{node_count}[/]")
        console.print(f"  · Edges: [bold]{edge_count}[/]")
        console.print(f"  · Database: [bold]{db_path}[/]")

    console.print("[dim]Next: codegraph why <file>:<line>  to view a decision card[/]")


app = typer.Typer(help="Index a codebase (tree-sitter + SQLite/Dgraph)")

if __name__ == "__main__":
    app()
