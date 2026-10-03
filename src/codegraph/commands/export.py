"""codegraph export: write an AI-agent context pack."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from codegraph.models import Decision, normalize_location_path, select_decisions
from codegraph.storage import (
    connect,
    db_path_for_root,
    query_all_decisions,
    query_nodes_at,
)

console = Console()


def load_context_data(scope: str) -> tuple[list, list[Decision]]:
    """Load nodes and decisions for the export scope."""
    db_path = db_path_for_root(Path.cwd())
    if not db_path.exists():
        return [], []
    now = datetime.now(timezone.utc)
    conn = connect(db_path)
    try:
        nodes = query_nodes_at(conn, now, scope)
        prefix = normalize_location_path(scope)
        decisions = select_decisions(query_all_decisions(conn))
        if prefix and prefix != ".":
            decisions = [d for d in decisions if (d.file_path or "").startswith(prefix)]
        return nodes, decisions
    finally:
        conn.close()


def build_context_markdown(nodes: list, decisions: list[Decision], scope: str) -> str:
    """Render the context pack markdown body."""
    lines: list[str] = [
        "# CodeGraph Context Pack",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Scope: {scope}",
        "",
    ]
    by_file: dict[str, list] = {}
    for node in nodes:
        by_file.setdefault(node.file_path, []).append(node)

    for file_path, file_nodes in sorted(by_file.items()):
        lines.append(f"## File: {file_path}")
        lines.append("")
        for node in file_nodes[:30]:
            start = getattr(node, "line_start", 0)
            end = getattr(node, "line_end", 0)
            name = getattr(node, "name", "?")
            lines.append(f"### CodeNode: {name} (lines {start}-{end})")
            related = _related_decisions(decisions, file_path, start, end)
            if related:
                lines.append("Related decisions:")
                for decision in related[:3]:
                    lines.append(f"- [{decision.uid[:12]}] {decision.content}")
                    if decision.reason:
                        lines.append(f"  Reason: {decision.reason[:160]}")
                    if decision.source_ref:
                        lines.append(f"  Source: {decision.source_ref}")
                    lines.append(f"  Status: {decision.status.value}")
                    if decision.constraints:
                        lines.append(f"  Constraint: {decision.constraints[0][:120]}")
            else:
                lines.append("Related decisions: (none indexed)")
            lines.append("")
    lines.append(
        "Paste this into Cursor/Claude/Copilot before editing these files."
    )
    lines.append("")
    return "\n".join(lines)


def _related_decisions(
    decisions: list[Decision], file_path: str, line_start: int, line_end: int
) -> list[Decision]:
    """Pick decisions bound to the file or covering a line in the node."""
    out: list[Decision] = []
    for decision in decisions:
        if decision.file_path == file_path or decision.file_path.startswith(file_path):
            out.append(decision)
            continue
        if decision.line is not None and decision.file_path == file_path:
            if line_start <= decision.line <= line_end:
                out.append(decision)
    return out


def export_command(
    for_ai: bool = typer.Option(
        False,
        "--for-ai",
        help="Write an AI-agent context pack",
    ),
    scope: str = typer.Option(
        ".",
        "--scope",
        help="Path scope, e.g. src or src/auth",
        metavar="PATH",
    ),
    output: Path = typer.Option(
        Path(".codegraph/context.md"),
        "--output",
        help="Output markdown path",
        metavar="PATH",
    ),
) -> None:
    """Export graph + decisions as an AI context pack.

    Args:
        for_ai: Must be true to write the pack (explicit intent).
        scope: Path prefix scope.
        output: Destination markdown file.
    """
    if not for_ai:
        console.print("[bold red]Invalid argument[/] Use --for-ai to export a context pack")
        raise typer.Exit(code=2)

    nodes, decisions = load_context_data(scope)
    text = build_context_markdown(nodes, decisions, scope)
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    console.print(f"[bold green]Context pack written[/] {output}")
    console.print(f"  · CodeNodes: [bold]{len(nodes)}[/]")
    console.print(f"  · Decisions: [bold]{len(decisions)}[/]")
    console.print("[dim]Paste this into Cursor/Claude/Copilot before editing these files.[/]")


app = typer.Typer(help="Export an AI-agent context pack")

if __name__ == "__main__":
    app()
