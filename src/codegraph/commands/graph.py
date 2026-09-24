"""codegraph graph: real time-travel code-graph snapshot."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.models import SAMPLE_DECISIONS, CodeNode, Decision
from codegraph.storage import (
    connect,
    count_edges_at,
    db_path_for_root,
    query_nodes_at,
)

console = Console()


class DateError(ValueError):
    """Date string is invalid."""


def parse_date(raw: str) -> date:
    """Parse YYYY-MM-DD date string."""
    value = raw.strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DateError(f"Date '{raw}' is invalid. Use YYYY-MM-DD, e.g. 2024-11-02") from exc


def filter_decisions_at(decisions: list[Decision], at: date) -> list[Decision]:
    """Return decisions created on or before the given date."""
    return [d for d in decisions if d.timestamp.date() <= at]


def load_snapshot_sqlite(
    root: Path, at: date, scope: str
) -> tuple[int, int, int, list[str], list[Decision]]:
    """Load a historical snapshot from SQLite."""
    db_path = db_path_for_root(root)
    at_dt = datetime(at.year, at.month, at.day, 23, 59, 59)
    if not db_path.exists():
        decisions = filter_decisions_at(SAMPLE_DECISIONS, at)
        return 0, 0, len(decisions), [], decisions

    conn = connect(db_path)
    try:
        nodes = query_nodes_at(conn, at_dt, scope)
        decisions = filter_decisions_at(_load_decisions(conn, scope), at)
        # Deduplicate symbol versions for a readable summary (keep newest range).
        summary = _unique_node_summaries(nodes)
        edge_count = count_edges_at(conn, at_dt, scope)
        return (
            len(nodes),
            edge_count,
            len(decisions),
            summary,
            decisions,
        )
    finally:
        conn.close()


def _unique_node_summaries(nodes: list[CodeNode]) -> list[str]:
    """Return one summary line per (file, name), preferring the tightest range."""
    best: dict[tuple[str, str], CodeNode] = {}
    for node in nodes:
        key = (node.file_path, node.name)
        prev = best.get(key)
        if prev is None or (node.line_end - node.line_start) < (prev.line_end - prev.line_start):
            best[key] = node
    lines = [
        f"{n.kind} {n.name} @ {n.file_path}:{n.line_start}-{n.line_end}"
        for n in best.values()
    ]
    return lines[:8]


def _load_decisions(conn, scope: str) -> list[Decision]:
    """Load decisions from DB, optionally filtered by scope prefix."""
    from codegraph.storage import query_all_decisions

    rows = query_all_decisions(conn)
    prefix = (scope or "").replace("\\", "/").rstrip("/")
    if prefix and prefix != ".":
        rows = [d for d in rows if d.file_path.startswith(prefix)]
    return rows


def summarize_changes(at: date, sample_nodes: list[str], decisions: list[Decision]) -> list[str]:
    """Build a short change summary for the snapshot date."""
    lines: list[str] = []
    for item in sample_nodes:
        lines.append(f"Structure: {item}")
    for decision in decisions:
        if decision.timestamp.date() == at:
            lines.append(f"Decision: {decision.content} ({decision.source_ref})")
    if not lines:
        lines.append(f"No nodes valid at {at.isoformat()} for this scope")
    return lines


def build_graph_table(
    at: date,
    scope: str,
    node_count: int,
    edge_count: int,
    decision_count: int,
) -> Table:
    """Build the code-graph summary table."""
    table = Table(
        title=f"Code graph snapshot · --at {at.isoformat()} · --scope {scope}",
        show_lines=False,
    )
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_column("Notes", style="dim")
    table.add_row(
        "Date",
        at.isoformat(),
        "valid_from <= date AND (valid_to is null OR valid_to >= date)",
    )
    table.add_row("Nodes", str(node_count), "CodeNode versions valid at date")
    table.add_row("Edges", str(edge_count), "edges with both endpoints valid at date")
    table.add_row("Decisions", str(decision_count), "Decision (not after this date)")
    return table


def graph_command(
    at: str = typer.Option(..., "--at", help="Snapshot date, format YYYY-MM-DD", metavar="DATE"),
    scope: str = typer.Option(
        ".",
        "--scope",
        help="Path scope, e.g. src or src/auth",
        metavar="PATH",
    ),
    backend: str = typer.Option(
        "sqlite",
        "--backend",
        help="Graph backend: sqlite | dgraph",
        metavar="BACKEND",
    ),
) -> None:
    """Print a code-graph snapshot for a historical date and scope.

    Args:
        at: Snapshot date (YYYY-MM-DD).
        scope: Path prefix scope.
        backend: Storage backend, sqlite (default) or dgraph.
    """
    try:
        at_date = parse_date(at)
    except DateError as exc:
        console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    if backend not in {"sqlite", "dgraph"}:
        console.print(
            f"[bold red]Invalid argument[/] Unknown backend: {backend} (use sqlite | dgraph)"
        )
        raise typer.Exit(code=2)

    root = Path.cwd()
    if backend == "dgraph":
        node_count, edge_count, decisions = _graph_from_dgraph(at_date, scope)
        sample: list[str] = []
        decision_count = len(decisions)
    else:
        node_count, edge_count, decision_count, sample, decisions = load_snapshot_sqlite(
            root, at_date, scope
        )

    console.print(build_graph_table(at_date, scope, node_count, edge_count, decision_count))
    console.print()
    console.print("[bold cyan]Change summary[/]")
    for line in summarize_changes(at_date, sample, decisions):
        console.print(f"  · {line}")


def _graph_from_dgraph(at: date, scope: str) -> tuple[int, int, list[Decision]]:
    """Query Dgraph time-travel snapshot."""
    from codegraph.graph import DgraphClient, DgraphConnectionError

    try:
        client = DgraphClient()
        if not client.ping():
            console.print(
                "[bold red]Dgraph connection failed[/] Cannot reach alpha. "
                "Run docker compose up -d first."
            )
            raise typer.Exit(code=3)
        payload = client.query_graph_at(at.isoformat(), scope)
        client.close()
    except DgraphConnectionError as exc:
        console.print(f"[bold red]Dgraph connection failed[/] {exc}")
        raise typer.Exit(code=3) from exc

    nodes = payload.get("nodes") or []
    edge_count = int(payload.get("edge_count") or 0)
    decisions = filter_decisions_at(SAMPLE_DECISIONS, at)
    return len(nodes), edge_count, decisions


app = typer.Typer(help="Historical code-graph snapshot (time travel)")

if __name__ == "__main__":
    app()
