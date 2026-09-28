"""codegraph conflicts: detect contradictory accepted decisions."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.decisions.conflicts import detect_all
from codegraph.models import Decision, Conflict, DecisionStatus, normalize_location_path
from codegraph.storage import connect, db_path_for_root, query_all_decisions

console = Console()

TYPE_LABEL = {
    "opposite": "OPPOSITE",
    "supersede": "SUPERSEDE",
    "temporal": "TEMPORAL",
}


def filter_scope(decisions: list[Decision], scope: str) -> list[Decision]:
    """Keep decisions whose file_path matches the scope prefix."""
    prefix = normalize_location_path(scope).strip("/")
    out: list[Decision] = []
    for d in decisions:
        if d.status != DecisionStatus.ACCEPTED:
            continue
        path = normalize_location_path(d.file_path or "").replace("\\", "/")
        if not prefix or prefix == ".":
            out.append(d)
        elif path and (path.startswith(prefix) or f"/{prefix}/" in f"/{path}"):
            out.append(d)
    return out


def load_decisions(backend: str) -> list[Decision]:
    """Load decisions from SQLite or Dgraph."""
    if backend == "dgraph":
        from codegraph.commands.why import decision_from_dgraph
        from codegraph.graph import DgraphClient, DgraphConnectionError

        try:
            client = DgraphClient()
            if not client.ping():
                console.print("[bold red]Dgraph connection failed[/] run docker compose up -d")
                raise typer.Exit(code=3)
            raw = client.query_all_decisions()
            client.close()
            return [decision_from_dgraph(x) for x in raw]
        except DgraphConnectionError as exc:
            console.print(f"[bold red]Dgraph connection failed[/] {exc}")
            raise typer.Exit(code=3) from exc

    db = db_path_for_root(Path.cwd())
    if not db.exists():
        return []
    conn = connect(db)
    try:
        return query_all_decisions(conn)
    finally:
        conn.close()


def _clip(text: str, n: int = 40) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def render_table(conflicts: list[Conflict], scope: str) -> None:
    """Render conflicts table + summary."""
    if not conflicts:
        console.print(f"[bold green]No conflicts detected[/] in scope={scope}")
        return

    table = Table(title=f"Decision conflicts · --scope {scope}")
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Decision A", overflow="fold")
    table.add_column("Decision B", overflow="fold")
    table.add_column("Location", style="dim")

    by_type: dict[str, int] = {}
    for c in conflicts:
        by_type[c.type] = by_type.get(c.type, 0) + 1
        table.add_row(
            TYPE_LABEL.get(c.type, c.type),
            _clip(c.decision_a.content),
            _clip(c.decision_b.content),
            c.location,
        )
    console.print(table)
    parts = [f"{by_type.get(k, 0)} {k}" for k in ("opposite", "supersede", "temporal")]
    console.print(f"\nSummary: {len(conflicts)} total · " + " · ".join(parts))


def render_json(conflicts: list[Conflict], scope: str) -> None:
    """Render conflicts as JSON."""
    by_type: dict[str, int] = {}
    for c in conflicts:
        by_type[c.type] = by_type.get(c.type, 0) + 1
    payload = {
        "scope": scope,
        "conflicts": [
            {
                "type": c.type,
                "decision_a": {
                    "uid": c.decision_a.uid,
                    "content": c.decision_a.content,
                    "source_ref": c.decision_a.source_ref,
                    "file_path": c.decision_a.file_path,
                    "status": c.decision_a.status.value,
                },
                "decision_b": {
                    "uid": c.decision_b.uid,
                    "content": c.decision_b.content,
                    "source_ref": c.decision_b.source_ref,
                    "file_path": c.decision_b.file_path,
                    "status": c.decision_b.status.value,
                },
                "location": c.location,
                "matched_words": c.matched_words,
                "explanation": c.explanation,
            }
            for c in conflicts
        ],
        "summary": {"total": len(conflicts), "by_type": by_type},
    }
    console.print_json(json.dumps(payload, ensure_ascii=False))


def conflicts_command(
    scope: str = typer.Option(".", "--scope", help="Path scope, e.g. docs/adr", metavar="PATH"),
    format: str = typer.Option("table", "--format", help="table | json", metavar="FMT"),
    backend: str = typer.Option("sqlite", "--backend", help="sqlite | dgraph", metavar="B"),
) -> None:
    """Detect contradictory accepted decisions in a scope."""
    if format not in {"table", "json"}:
        console.print("[bold red]Invalid argument[/] --format must be table or json")
        raise typer.Exit(code=2)
    if backend not in {"sqlite", "dgraph"}:
        console.print(f"[bold red]Invalid argument[/] Unknown backend: {backend}")
        raise typer.Exit(code=2)

    decisions = filter_scope(load_decisions(backend), scope)
    conflicts = detect_all(decisions)
    if format == "json":
        render_json(conflicts, scope)
    else:
        render_table(conflicts, scope)


app = typer.Typer(help="Detect contradictory accepted decisions")

if __name__ == "__main__":
    app()
