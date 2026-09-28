"""codegraph diff: decision changes between two versions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.git.refs import RefError, resolve_ref
from codegraph.models import Decision, DecisionChange
from codegraph.storage import connect, db_path_for_root, query_decisions_at

console = Console()

KIND_LABEL = {
    "added": "+ ADDED",
    "removed": "- REMOVED",
    "changed": "~ CHANGED",
    "superseded": "x SUPERSEDED",
}
KIND_ORDER = {"added": 0, "changed": 1, "superseded": 2, "removed": 3}


def compute_changes(
    from_decisions: list[Decision], to_decisions: list[Decision]
) -> list[DecisionChange]:
    """Compute added/removed/changed/superseded decision deltas."""
    old = {d.uid: d for d in from_decisions}
    new = {d.uid: d for d in to_decisions}
    out: list[DecisionChange] = []

    for uid, dec in new.items():
        if uid not in old:
            out.append(
                DecisionChange(kind="added", decision=dec, old_status=None, new_status=dec.status.value)
            )
            continue
        prev = old[uid]
        if prev.status != dec.status and dec.status.value == "superseded":
            out.append(
                DecisionChange(
                    kind="superseded",
                    decision=dec,
                    old_status=prev.status.value,
                    new_status=dec.status.value,
                )
            )
        elif prev.status != dec.status or prev.content != dec.content or prev.reason != dec.reason:
            out.append(
                DecisionChange(
                    kind="changed",
                    decision=dec,
                    old_status=prev.status.value,
                    new_status=dec.status.value,
                )
            )

    for uid, dec in old.items():
        if uid not in new:
            out.append(
                DecisionChange(kind="removed", decision=dec, old_status=dec.status.value, new_status=None)
            )

    out.sort(key=lambda c: (KIND_ORDER.get(c.kind, 9), c.decision.content))
    return out


def _scope_label(decision: Decision) -> str:
    path = decision.file_path or ""
    return path.rsplit("/", 1)[0] if "/" in path else (path or "(global)")


def render_table(from_ref: str, to_ref: str, scope: str, changes: list[DecisionChange]) -> None:
    """Print a Rich table of decision changes."""
    console.print(f"[bold]Decision changes:[/] {from_ref} → {to_ref}")
    console.print(f"Scope: {scope}\n")
    if not changes:
        console.print("[yellow]No decision changes in this range[/]")
        return

    table = Table(show_lines=False)
    table.add_column("Change", style="cyan", no_wrap=True)
    table.add_column("Decision", overflow="fold")
    table.add_column("Source", style="dim")
    table.add_column("Scope", style="dim")

    counts = {"added": 0, "changed": 0, "removed": 0, "superseded": 0}
    for ch in changes:
        counts[ch.kind] = counts.get(ch.kind, 0) + 1
        content = ch.decision.content
        if len(content) > 50:
            content = content[:47] + "..."
        date = ch.decision.timestamp.date().isoformat()
        source = f"{ch.decision.source_ref or ch.decision.source.value} · {date}"
        table.add_row(KIND_LABEL.get(ch.kind, ch.kind), content, source, _scope_label(ch.decision))

    console.print(table)
    summary = (
        f"{counts.get('added', 0)} added · {counts.get('changed', 0)} changed · "
        f"{counts.get('removed', 0)} removed · {counts.get('superseded', 0)} superseded"
    )
    console.print(f"\nSummary: {summary}")


def render_json(changes: list[DecisionChange]) -> None:
    """Print JSON payload."""
    payload = {
        "changes": [
            {
                "kind": c.kind,
                "content": c.decision.content,
                "reason": c.decision.reason,
                "source": c.decision.source.value,
                "source_ref": c.decision.source_ref,
                "status": c.decision.status.value,
                "old_status": c.old_status,
                "new_status": c.new_status,
                "file_path": c.decision.file_path,
                "timestamp": c.decision.timestamp.isoformat(),
            }
            for c in changes
        ],
        "summary": {
            "added": sum(1 for c in changes if c.kind == "added"),
            "changed": sum(1 for c in changes if c.kind == "changed"),
            "removed": sum(1 for c in changes if c.kind == "removed"),
            "superseded": sum(1 for c in changes if c.kind == "superseded"),
        },
    }
    console.print_json(json.dumps(payload, ensure_ascii=False))


def diff_command(
    from_ref: str = typer.Argument(..., help="Start version (tag / sha / YYYY-MM-DD)"),
    to_ref: str = typer.Argument(..., help="End version (tag / sha / YYYY-MM-DD)"),
    scope: str = typer.Option(".", "--scope", help="Path prefix scope", metavar="PATH"),
    format: str = typer.Option("table", "--format", help="table | json", metavar="FMT"),
    backend: str = typer.Option("sqlite", "--backend", help="sqlite | dgraph", metavar="B"),
) -> None:
    """Show decision changes between two versions."""
    if format not in {"table", "json"}:
        console.print(f"[bold red]Invalid argument[/] --format must be table or json")
        raise typer.Exit(code=2)
    if backend not in {"sqlite", "dgraph"}:
        console.print(f"[bold red]Invalid argument[/] Unknown backend: {backend}")
        raise typer.Exit(code=2)

    root = Path.cwd()
    try:
        from_sha, from_ts = resolve_ref(root, from_ref)
        to_sha, to_ts = resolve_ref(root, to_ref)
    except RefError as exc:
        console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    if from_ts > to_ts:
        console.print("[bold red]Invalid argument[/] from must be earlier than to")
        raise typer.Exit(code=2)

    if backend == "dgraph":
        console.print("[bold red]Dgraph backend not implemented for diff yet[/]")
        raise typer.Exit(code=3)

    db_path = db_path_for_root(root)
    if not db_path.exists():
        console.print("[bold red]No index found[/] Run codegraph index first")
        raise typer.Exit(code=1)

    conn = connect(db_path)
    try:
        from_decs = query_decisions_at(conn, from_ts, scope)
        to_decs = query_decisions_at(conn, to_ts, scope)
    finally:
        conn.close()

    if not from_decs and not to_decs:
        console.print("[yellow]No decisions in scope[/]")
        raise typer.Exit(code=0)

    changes = compute_changes(from_decs, to_decs)
    if format == "json":
        render_json(changes)
    else:
        render_table(from_ref, to_ref, scope, changes)


app = typer.Typer(help="Diff decisions between two versions")

if __name__ == "__main__":
    app()
