"""codegraph conflicts: find contradictory accepted decisions."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.models import Decision, DecisionStatus, normalize_location_path
from codegraph.storage import connect, db_path_for_root, query_all_decisions

console = Console()

# Opposite word pairs used by the rule engine (no LLM).
OPPOSITE_PAIRS: tuple[tuple[str, str], ...] = (
    ("use", "avoid"),
    ("always", "never"),
    ("enable", "disable"),
    ("add", "remove"),
    ("allow", "forbid"),
    ("keep", "drop"),
    ("require", "optional"),
)


def _words(text: str) -> set[str]:
    """Lowercase alphanumeric tokens."""
    return {w for w in __import__("re").findall(r"[a-z][a-z0-9_\-]*", text.lower())}


def reasons_conflict(a: Decision, b: Decision) -> str | None:
    """Return a conflict reason when two decisions contradict via opposite words."""
    wa = _words(f"{a.content} {a.reason}")
    wb = _words(f"{b.content} {b.reason}")
    for left, right in OPPOSITE_PAIRS:
        if (left in wa and right in wb) or (right in wa and left in wb):
            return f"opposite terms '{left}' vs '{right}'"
    if (
        a.uid != b.uid
        and "supersede" in b.reason.lower()
        and a.status == DecisionStatus.ACCEPTED
        and b.status == DecisionStatus.ACCEPTED
    ):
        return "claimed supersede but both still accepted"
    return None


def group_by_scope(decisions: list[Decision], scope: str) -> dict[str, list[Decision]]:
    """Group accepted decisions by file_path within scope."""
    prefix = normalize_location_path(scope)
    groups: dict[str, list[Decision]] = {}
    for decision in decisions:
        if decision.status != DecisionStatus.ACCEPTED:
            continue
        path = decision.file_path or "(global)"
        if prefix and prefix != "." and not path.startswith(prefix):
            continue
        groups.setdefault(path, []).append(decision)
    return groups


def find_conflicts(decisions: list[Decision], scope: str) -> list[tuple[Decision, Decision, str]]:
    """Find conflicting decision pairs under a scope."""
    pairs: list[tuple[Decision, Decision, str]] = []
    for _, group in group_by_scope(decisions, scope).items():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                reason = reasons_conflict(a, b)
                if reason:
                    pairs.append((a, b, reason))
    return pairs


def load_decisions(backend: str) -> list[Decision]:
    """Load decisions from SQLite or Dgraph."""
    if backend == "dgraph":
        from codegraph.commands.why import decision_from_dgraph
        from codegraph.graph import DgraphClient, DgraphConnectionError

        try:
            client = DgraphClient()
            if not client.ping():
                console.print(
                    "[bold red]Dgraph connection failed[/] Cannot reach alpha. "
                    "Run docker compose up -d first."
                )
                raise typer.Exit(code=3)
            raw = client.query_all_decisions()
            client.close()
            return [decision_from_dgraph(item) for item in raw]
        except DgraphConnectionError as exc:
            console.print(f"[bold red]Dgraph connection failed[/] {exc}")
            raise typer.Exit(code=3) from exc

    db_path = db_path_for_root(Path.cwd())
    if not db_path.exists():
        return []
    conn = connect(db_path)
    try:
        return query_all_decisions(conn)
    finally:
        conn.close()


def conflicts_command(
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
    """Detect contradictory accepted decisions in a scope.

    Args:
        scope: Path prefix scope.
        backend: Storage backend, sqlite (default) or dgraph.
    """
    if backend not in {"sqlite", "dgraph"}:
        console.print(
            f"[bold red]Invalid argument[/] Unknown backend: {backend} (use sqlite | dgraph)"
        )
        raise typer.Exit(code=2)

    decisions = load_decisions(backend)
    pairs = find_conflicts(decisions, scope)

    table = Table(title=f"Decision conflicts · --scope {scope}")
    table.add_column("Decision A", style="yellow", overflow="fold")
    table.add_column("Decision B", style="yellow", overflow="fold")
    table.add_column("Why conflict", style="red")

    if not pairs:
        console.print("[bold green]No conflicts found[/] for accepted decisions in scope.")
        return

    for a, b, reason in pairs:
        table.add_row(
            f"{a.uid[:20]} {a.content[:48]}",
            f"{b.uid[:20]} {b.content[:48]}",
            reason,
        )
    console.print(table)


app = typer.Typer(help="Find contradictory accepted decisions")

if __name__ == "__main__":
    app()
