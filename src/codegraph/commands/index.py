"""codegraph index: parse sources across Git history and persist the graph."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from codegraph.decisions.sources import extract_all
from codegraph.git.history import CommitInfo, GitHistory
from codegraph.models import (
    SAMPLE_DECISIONS,
    CodeNode,
    Decision,
    Edge,
    make_uid,
    normalize_location_path,
)
from codegraph.parser.registry import get_parser_for_path, is_supported_source
from codegraph.storage import (
    clear_graph,
    connect,
    count_decisions,
    count_edges,
    count_nodes,
    db_path_for_root,
    init_schema,
    insert_decisions,
    insert_edges,
    insert_nodes,
)

console = Console()
logger = logging.getLogger(__name__)

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
    "target",
    ".cargo",
    "vendor",
}

INDEX_STEPS: list[str] = [
    "Walk Git history",
    "Parse snapshots with tree-sitter",
    "Extract decisions from commits/ADRs",
    "Write graph store",
]


def resolve_repo_path(path: Path) -> Path:
    """Resolve and validate the repository path."""
    target = path.expanduser().resolve()
    if not target.exists():
        raise typer.BadParameter(f"Path not found: {path}")
    return target


def is_skipped_path(root: Path, file_path: str) -> bool:
    """Return True when a repo-relative path should be ignored."""
    parts = Path(file_path).parts
    return any(part in SKIP_DIRS for part in parts)


def parse_source_text(path_str: str, text: str) -> tuple[list[CodeNode], list[Edge]]:
    """Parse in-memory source text into nodes and edges."""
    tmp_suffix = Path(path_str).suffix or ".txt"
    parser = get_parser_for_path(Path(path_str))
    if parser is None:
        return [], []
    # Tree-sitter parsers read from disk; use a side channel via monkeypatch-like temp parse.
    nodes = parser.parse_text(path_str, text) if hasattr(parser, "parse_text") else []
    edges = parser.extract_edges(nodes) if nodes else []
    return nodes, edges


def close_previous_versions(
    live: dict[tuple[str, str], list[CodeNode]],
    key: tuple[str, str],
    when: datetime,
) -> None:
    """Set valid_to on open node versions for a (file, name) key."""
    for node in live.get(key, []):
        if node.valid_to is None:
            node.valid_to = when


def ingest_commit(
    history: GitHistory,
    commit: CommitInfo,
    live: dict[tuple[str, str], list[CodeNode]],
    all_nodes: list[CodeNode],
    all_edges: list[Edge],
) -> None:
    """Parse changed source files at one commit and version nodes."""
    for rel in commit.changed_files:
        rel_n = normalize_location_path(rel)
        if is_skipped_path(history.root, rel_n) or not is_supported_source(Path(rel_n)):
            continue
        text = history.get_file_at_commit(commit.sha, rel_n)
        if not text:
            close_previous_versions(live, (rel_n, "*"), commit.timestamp)
            # close all nodes in that file
            for key in [k for k in live if k[0] == rel_n]:
                close_previous_versions(live, key, commit.timestamp)
            continue

        parser = get_parser_for_path(Path(rel_n))
        if parser is None:
            continue
        try:
            nodes = parser.parse_text(rel_n, text, commit_sha=commit.sha, valid_from=commit.timestamp)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parse failed at %s %s: %s", commit.sha[:10], rel_n, exc)
            continue

        seen_names = {(n.file_path, n.name) for n in nodes}
        for key in [k for k in live if k[0] == rel_n and (k[0], k[1]) not in seen_names]:
            close_previous_versions(live, key, commit.timestamp)

        for node in nodes:
            key = (node.file_path, node.name)
            # Close older version of the same symbol when lines change
            for prev in live.get(key, []):
                if prev.valid_to is None and (
                    prev.line_start != node.line_start or prev.line_end != node.line_end
                ):
                    prev.valid_to = commit.timestamp
            live.setdefault(key, []).append(node)
            all_nodes.append(node)

        try:
            all_edges.extend(parser.extract_edges(nodes))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Edge extract failed for %s: %s", rel_n, exc)


def build_edges_for_nodes(nodes: list[CodeNode]) -> list[Edge]:
    """Fallback edge builder when parsers do not emit cross-file edges."""
    by_uid = {n.uid: n for n in nodes}
    edges: list[Edge] = []
    for node in nodes:
        if node.parent_uid and node.parent_uid in by_uid:
            edges.append(
                Edge(
                    from_uid=node.parent_uid,
                    to_uid=node.uid,
                    kind="contains",
                    file_path=node.file_path,
                    line=node.line_start,
                )
            )
    return edges


def load_decisions(
    repo_path: Path, depth: int, use_llm: bool = False, llm_model: str = "llama3.2"
) -> list[Decision]:
    """Extract real decisions; fall back to samples when empty."""
    decisions = extract_all(
        repo_path, depth=depth, use_llm=use_llm, llm_model=llm_model
    )
    if decisions:
        return decisions
    console.print(
        "[yellow]warn[/] No commit/ADR decisions found; storing bundled sample decisions"
    )
    return list(SAMPLE_DECISIONS)


def _ingest_working_tree(
    root: Path, all_nodes: list[CodeNode], all_edges: list[Edge]
) -> None:
    """Parse files currently on disk when Git history is unavailable."""
    from codegraph.parser.registry import is_supported_source

    now = datetime.now(timezone.utc)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_supported_source(path):
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        rel = normalize_location_path(str(path.relative_to(root)))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Read failed %s: %s", path, exc)
            continue
        parser = get_parser_for_path(Path(rel))
        if parser is None:
            continue
        try:
            nodes = parser.parse_text(rel, text, commit_sha="WORKTREE", valid_from=now)
            all_nodes.extend(nodes)
            all_edges.extend(parser.extract_edges(nodes))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parse failed %s: %s", rel, exc)


def write_sqlite_graph(
    db_path: Path,
    nodes: list[CodeNode],
    edges: list[Edge],
    decisions: list[Decision],
) -> tuple[int, int, int]:
    """Persist nodes/edges/decisions and return counts."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        clear_graph(conn)
        insert_nodes(conn, nodes)
        insert_edges(conn, edges)
        insert_decisions(conn, decisions)
        return count_nodes(conn), count_edges(conn), count_decisions(conn)
    finally:
        conn.close()


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
            task = progress.add_task(step, total=6)
            for _ in range(6):
                progress.update(task, advance=1)
            progress.update(overall, advance=1)


def index_command(
    path: Path = typer.Argument(..., help="Repository or directory path to index", metavar="PATH"),
    depth: int = typer.Option(
        100,
        "--depth",
        help="How many recent commits to walk (default 100)",
        metavar="N",
    ),
    backend: str = typer.Option(
        "sqlite",
        "--backend",
        help="Graph backend: sqlite | dgraph",
        metavar="BACKEND",
    ),
    use_llm: bool = typer.Option(
        False,
        "--use-llm",
        help="Use local Ollama to extract decisions when rules miss",
    ),
    llm_model: str = typer.Option(
        "llama3.2",
        "--llm-model",
        help="Ollama model name for --use-llm",
        metavar="MODEL",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON summary",
    ),
) -> None:
    """Parse Git history with tree-sitter and persist the code graph.

    Args:
        path: Repository root or subdirectory.
        depth: Max commits to walk.
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
    console.print(
        f"[bold cyan]Indexing[/] {target} ... [dim]backend={backend} depth={depth}[/]"
    )
    run_index_progress(INDEX_STEPS)

    all_nodes: list[CodeNode] = []
    all_edges: list[Edge] = []
    live: dict[tuple[str, str], list[CodeNode]] = {}
    commit_count = 0

    try:
        history = GitHistory(root)
    except ValueError as exc:
        console.print(f"[yellow]warn[/] {exc}; parsing working tree only")
        history = None

    if history is not None:
        commits = list(history.iter_commits(depth=depth))
        for commit in reversed(commits):
            try:
                ingest_commit(history, commit, live, all_nodes, all_edges)
                commit_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skip commit %s: %s", commit.sha, exc)

    if not all_nodes:
        _ingest_working_tree(root, all_nodes, all_edges)

    if use_llm:
        console.print(
            f"[yellow]warn[/] --use-llm enabled (model={llm_model}); "
            "falls back to rules if Ollama is down"
        )
    decisions = load_decisions(root, depth, use_llm=use_llm, llm_model=llm_model)

    if backend == "dgraph":
        _write_dgraph(all_nodes, all_edges, decisions)
        node_count, edge_count = len(all_nodes), len(all_edges)
        decision_count = len(decisions)
    else:
        db_path = db_path_for_root(root)
        node_count, edge_count, decision_count = write_sqlite_graph(
            db_path, all_nodes, all_edges, decisions
        )

    if as_json:
        import json as jsonlib

        typer.echo(
            jsonlib.dumps(
                {
                    "root": str(root),
                    "backend": backend,
                    "commits": commit_count,
                    "nodes": node_count,
                    "edges": edge_count,
                    "decisions": decision_count,
                },
                ensure_ascii=False,
            )
        )
        return

    console.print()
    console.print(f"[bold green]Index complete[/]  [bold]{root}[/]")
    console.print(f"  · Commits walked: [bold]{commit_count}[/]")
    console.print(f"  · Nodes: [bold]{node_count}[/]")
    console.print(f"  · Edges: [bold]{edge_count}[/]")
    console.print(f"  · Decisions: [bold]{decision_count}[/]")
    if backend == "dgraph":
        console.print(
            "  · Dgraph UI: "
            "[link=http://localhost:8080/?latest]http://localhost:8080/?latest[/link]"
        )
    else:
        console.print(f"  · Database: [bold]{db_path_for_root(root)}[/]")
    console.print("[dim]Next: codegraph why <file>:<line>  to view a decision card[/]")


def _write_dgraph(nodes: list[CodeNode], edges: list[Edge], decisions: list[Decision]) -> None:
    """Write the graph to Dgraph when requested."""
    from codegraph.graph import DgraphClient, DgraphConnectionError

    try:
        client = DgraphClient()
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
        for decision in decisions:
            client.upsert_decision(decision)
        client.close()
    except typer.Exit:
        raise
    except DgraphConnectionError as exc:
        console.print(f"[bold red]Dgraph connection failed[/] {exc}")
        raise typer.Exit(code=3) from exc


app = typer.Typer(help="Index a codebase from Git history (tree-sitter + SQLite/Dgraph)")

if __name__ == "__main__":
    app()
