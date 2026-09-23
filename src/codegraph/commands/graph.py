"""codegraph graph: historical code-graph snapshot."""

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
            f"Date '{raw}' is invalid. Use YYYY-MM-DD, e.g. 2024-11-02"
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
            lines.append(f"Decision: {decision.content} ({decision.source_ref})")
    if not lines:
        lines.append(f"No extra changes at {at.isoformat()}; returning baseline graph")
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
        title=f"Code graph snapshot · --at {at.isoformat()} · --scope {scope}",
        show_lines=False,
    )
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_column("Notes", style="dim")
    table.add_row("Date", at.isoformat(), "Empty valid_to means currently active")
    table.add_row("Nodes", str(node_count), "CodeNode")
    table.add_row("Edges", str(edge_count), "uses / defined_by / contains")
    table.add_row("Decisions", str(len(decisions)), "Decision (not after this date)")
    return table


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

    if backend == "dgraph":
        node_count, edge_count, decisions = _graph_from_dgraph(at_date, scope)
    else:
        decisions = filter_decisions_at(SAMPLE_DECISIONS, at_date)
        stats = load_sqlite_stats()
        node_count, edge_count = stats if stats else (0, 0)

    console.print(build_graph_table(at_date, scope, node_count, edge_count, decisions))
    console.print()
    console.print("[bold cyan]Change summary[/]")
    for line in summarize_changes(at_date, decisions):
        console.print(f"  · {line}")


app = typer.Typer(help="Historical code-graph snapshot")

if __name__ == "__main__":
    app()
