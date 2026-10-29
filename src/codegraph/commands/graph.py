"""codegraph graph: real time-travel code-graph snapshot."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.models import CodeNode, Decision, decision_to_dict, select_decisions
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


def local_day_end(day: date) -> datetime:
    """Return the last instant of a local calendar day as an aware UTC datetime.

    Stored `valid_from` / `valid_to` values are UTC ISO strings, so the query
    boundary has to be UTC too. Treating local midnight as if it were UTC put the
    cut-off eight hours late east of Greenwich.
    """
    return datetime.combine(day, time(23, 59, 59)).astimezone(timezone.utc)


def filter_decisions_at(decisions: list[Decision], at: date) -> list[Decision]:
    """Return decisions created on or before the given local date."""
    return [d for d in decisions if d.timestamp.astimezone().date() <= at]


def load_snapshot_sqlite(
    root: Path, at: date, scope: str
) -> tuple[int, int, int, list[str], list[Decision]]:
    """Load a historical snapshot from SQLite."""
    db_path = db_path_for_root(root)
    at_dt = local_day_end(at)
    if not db_path.exists():
        return 0, 0, 0, [], []

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

    rows = select_decisions(query_all_decisions(conn))
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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of a table",
    ),
) -> None:
    """Print a code-graph snapshot for a historical date and scope.

    Args:
        at: Snapshot date (YYYY-MM-DD).
        scope: Path prefix scope.
        as_json: Emit JSON for editors and scripts.
    """
    try:
        at_date = parse_date(at)
    except DateError as exc:
        console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    root = Path.cwd()
    node_count, edge_count, decision_count, sample, decisions = load_snapshot_sqlite(
        root, at_date, scope
    )

    if as_json:
        import json as jsonlib

        payload = {
            "date": at_date.isoformat(),
            "scope": scope,
            "nodes": node_count,
            "edges": edge_count,
            "decisions": decision_count,
            "summary": summarize_changes(at_date, sample, decisions),
            "decision_records": [decision_to_dict(d) for d in decisions],
        }
        typer.echo(jsonlib.dumps(payload, ensure_ascii=False, indent=2))
        return

    console.print(build_graph_table(at_date, scope, node_count, edge_count, decision_count))
    console.print()
    console.print("[bold cyan]Change summary[/]")
    for line in summarize_changes(at_date, sample, decisions):
        console.print(f"  · {line}")


app = typer.Typer(help="Historical code-graph snapshot (time travel)")

if __name__ == "__main__":
    app()
