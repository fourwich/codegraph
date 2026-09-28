"""codegraph conflicts: find contradictory accepted decisions."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codegraph.models import Decision, DecisionStatus, normalize_location_path
from codegraph.storage import connect, db_path_for_root, query_all_decisions

console = Console()

# Opposite word pairs used by the rule engine (no LLM).
OPPOSITE_PAIRS: tuple[tuple[str, str], ...] = (
    ("stateful", "stateless"),
    ("sticky", "stateless"),
    ("always", "never"),
    ("enable", "disable"),
    ("add", "remove"),
    ("allow", "forbid"),
    ("keep", "drop"),
    ("require", "optional"),
    ("revoke", "immutable"),
)

# Multi-word phrases that contradict when both appear.
OPPOSITE_PHRASES: tuple[tuple[str, str], ...] = (
    ("session state", "never store session"),
    ("denylist", "never store"),
    ("server-side denylist", "stateless jwt"),
    ("server-side denylist", "no server"),
)


def _words(text: str) -> set[str]:
    """Lowercase alphanumeric tokens."""
    return set(re.findall(r"[a-z][a-z0-9_\-]*", text.lower()))


def _blob(a: Decision, b: Decision | None = None) -> str:
    parts = [a.content, a.reason, " ".join(a.alternatives), " ".join(a.constraints)]
    if b is not None:
        parts.extend([b.content, b.reason, " ".join(b.alternatives), " ".join(b.constraints)])
    return " ".join(parts).lower()


def reasons_conflict(a: Decision, b: Decision) -> str | None:
    """Return a conflict reason when two decisions contradict."""
    wa = _words(_blob(a))
    wb = _words(_blob(b))
    for left, right in OPPOSITE_PAIRS:
        if (left in wa and right in wb) or (right in wa and left in wb):
            return f"opposite terms '{left}' vs '{right}'"

    ba = _blob(a)
    bb = _blob(b)
    for left, right in OPPOSITE_PHRASES:
        if (left in ba and right in bb) or (right in ba and left in bb):
            return f"opposite phrases '{left}' vs '{right}'"

    if (
        a.uid != b.uid
        and "supersede" in b.reason.lower()
        and a.status == DecisionStatus.ACCEPTED
        and b.status == DecisionStatus.ACCEPTED
    ):
        return "claimed supersede but both still accepted"
    return None


def filter_by_scope(decisions: list[Decision], scope: str) -> list[Decision]:
    """Filter accepted decisions under a path prefix (empty path = global)."""
    prefix = normalize_location_path(scope).strip("/")
    out: list[Decision] = []
    for decision in decisions:
        if decision.status != DecisionStatus.ACCEPTED:
            continue
        path = normalize_location_path(decision.file_path or "").replace("\\", "/")
        if not prefix or prefix == ".":
            out.append(decision)
            continue
        # Accept relative prefixes against absolute or relative stored paths.
        if (
            not path
            or path.startswith(prefix)
            or path.endswith("/" + prefix)
            or f"/{prefix}/" in f"/{path}"
        ):
            out.append(decision)
    return out


def find_conflicts(decisions: list[Decision], scope: str) -> list[tuple[Decision, Decision, str]]:
    """Find conflicting decision pairs in scope (cross-file included)."""
    group = filter_by_scope(decisions, scope)
    pairs: list[tuple[Decision, Decision, str]] = []
    for i, a in enumerate(group):
        for b in group[i + 1 :]:
            if a.uid == b.uid:
                continue
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


def _clip(text: str, n: int = 42) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def render_table(pairs: list[tuple[Decision, Decision, str]], scope: str) -> None:
    """Print conflicts as a Rich table."""
    if not pairs:
        console.print("[bold green]No conflicts found[/] for accepted decisions in scope.")
        return

    table = Table(title=f"Decision conflicts · --scope {scope}")
    table.add_column("Decision A", style="yellow", overflow="fold")
    table.add_column("Decision B", style="yellow", overflow="fold")
    table.add_column("Why conflict", style="red")

    for a, b, reason in pairs:
        table.add_row(
            f"{_clip(a.content)}\n{a.source_ref}",
            f"{_clip(b.content)}\n{b.source_ref}",
            reason,
        )
    console.print(table)
    console.print(
        f"\nSummary: {len(pairs)} conflict pair(s) · "
        f"{len({p[0].uid for p in pairs} | {p[1].uid for p in pairs})} decisions involved"
    )


def render_json(pairs: list[tuple[Decision, Decision, str]]) -> None:
    """Print conflicts as JSON."""
    payload = {
        "conflicts": [
            {
                "a": {
                    "uid": a.uid,
                    "content": a.content,
                    "source_ref": a.source_ref,
                    "file_path": a.file_path,
                    "status": a.status.value,
                },
                "b": {
                    "uid": b.uid,
                    "content": b.content,
                    "source_ref": b.source_ref,
                    "file_path": b.file_path,
                    "status": b.status.value,
                },
                "reason": reason,
            }
            for a, b, reason in pairs
        ],
        "summary": {"pairs": len(pairs)},
    }
    console.print_json(json.dumps(payload, ensure_ascii=False))


def conflicts_command(
    scope: str = typer.Option(
        ".",
        "--scope",
        help="Path scope, e.g. src or docs/adr",
        metavar="PATH",
    ),
    format: str = typer.Option("table", "--format", help="table | json", metavar="FMT"),
    backend: str = typer.Option(
        "sqlite",
        "--backend",
        help="Graph backend: sqlite | dgraph",
        metavar="BACKEND",
    ),
) -> None:
    """Detect contradictory accepted decisions in a scope."""
    if backend not in {"sqlite", "dgraph"}:
        console.print(f"[bold red]Invalid argument[/] Unknown backend: {backend}")
        raise typer.Exit(code=2)
    if format not in {"table", "json"}:
        console.print("[bold red]Invalid argument[/] --format must be table or json")
        raise typer.Exit(code=2)

    decisions = load_decisions(backend)
    pairs = find_conflicts(decisions, scope)
    if format == "json":
        render_json(pairs)
    else:
        render_table(pairs, scope)


app = typer.Typer(help="Find contradictory accepted decisions")

if __name__ == "__main__":
    app()
