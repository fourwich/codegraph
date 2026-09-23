"""codegraph why: decision provenance for a source location."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codegraph.models import (
    CodeNode,
    Decision,
    DecisionSource,
    DecisionStatus,
    find_decisions_for_file,
    find_decisions_for_location,
    normalize_location_path,
)
from codegraph.storage import (
    connect,
    db_path_for_root,
    find_node_at_line,
    query_decisions_for_file,
    query_decisions_for_line,
)

console = Console()

LOCATION_RE = re.compile(r"^(?P<file>.+):(?P<line>\d+)$")


class LocationError(ValueError):
    """User-supplied file:line is invalid."""


def parse_location(raw: str) -> tuple[str, int]:
    """Parse `file:line` into (path, line)."""
    value = raw.strip()
    if not value:
        raise LocationError("Location cannot be empty. Use the form src/auth/session.ts:42")
    match = LOCATION_RE.match(value)
    if not match:
        raise LocationError(
            f"Cannot parse location '{raw}'. Expected path:line, e.g. src/auth/session.ts:42"
        )
    line_no = int(match.group("line"))
    if line_no < 1:
        raise LocationError(f"Line number must be >= 1, got: {line_no}")
    return normalize_location_path(match.group("file")), line_no


def format_status_label(status_value: str) -> str:
    """Map decision status to a short label."""
    mapping = {
        "accepted": "✅ active",
        "superseded": "🔁 superseded",
        "rejected": "⛔ rejected",
    }
    return mapping.get(status_value, status_value)


def format_confidence(confidence: float) -> str:
    """Format 0-1 confidence as stars and percent."""
    percent = int(round(confidence * 100))
    stars = "★" * int(round(confidence * 5)) + "☆" * (5 - int(round(confidence * 5)))
    return f"{stars}  {percent}%"


def load_code_node_sqlite(file_path: str, line: int, root: Path | None = None) -> CodeNode | None:
    """Load covering CodeNode from SQLite if an index exists."""
    db_path = db_path_for_root(root or Path.cwd())
    if not db_path.exists():
        return None
    try:
        conn = connect(db_path)
    except sqlite3.Error as exc:
        console.print(f"[yellow]warn[/] Cannot open graph database {db_path}: {exc}")
        return None
    try:
        return find_node_at_line(conn, file_path, line)
    finally:
        conn.close()


def load_decisions_sqlite(
    file_path: str, line: int, root: Path | None = None, commit_sha: str = ""
) -> list[Decision]:
    """Load extracted decisions from SQLite, with sample fallback."""
    db_path = db_path_for_root(root or Path.cwd())
    rows: list[Decision] = []
    if db_path.exists():
        try:
            conn = connect(db_path)
        except sqlite3.Error as exc:
            console.print(f"[yellow]warn[/] Cannot open graph database {db_path}: {exc}")
            return find_decisions_for_location(file_path, line)
        try:
            rows = query_decisions_for_line(conn, file_path, line)
            if not rows:
                rows = query_decisions_for_file(conn, file_path)
            if not rows and commit_sha:
                rows = [
                    d
                    for d in _all_decisions(conn)
                    if commit_sha[:10] in d.source_ref or commit_sha in d.source_ref
                ]
        finally:
            conn.close()
    if rows:
        return rows
    samples = find_decisions_for_location(file_path, line)
    if samples:
        return samples
    if commit_sha and not rows:
        return []
    return samples


def _all_decisions(conn) -> list[Decision]:
    """Return every stored decision."""
    from codegraph.storage import query_all_decisions

    return query_all_decisions(conn)


def _parse_ts(value: object) -> datetime:
    """Parse an ISO timestamp or fall back to now."""
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def decision_from_dgraph(raw: dict) -> Decision:
    """Convert a Dgraph Decision dict into the pydantic model."""
    status = str(raw.get("status") or "accepted")
    source = str(raw.get("source") or "adr")
    return Decision(
        uid=str(raw.get("uid") or raw.get("decision_uid") or "dec"),
        content=str(raw.get("content") or ""),
        reason=str(raw.get("reason") or ""),
        alternatives=list(raw.get("alternatives") or []),
        status=DecisionStatus(status)
        if status in DecisionStatus._value2member_map_
        else DecisionStatus.ACCEPTED,
        source=DecisionSource(source)
        if source in DecisionSource._value2member_map_
        else DecisionSource.ADR,
        source_ref=str(raw.get("source_ref") or ""),
        timestamp=_parse_ts(raw.get("timestamp")),
        author=str(raw.get("author") or ""),
        file_path=str(raw.get("file_path") or ""),
        line=int(raw["line"]) if raw.get("line") is not None else None,
        constraints=list(raw.get("constraints") or []),
        confidence=float(raw.get("confidence") or 0.8),
    )


def render_code_node_header(node: CodeNode) -> None:
    """Render the hit CodeNode summary at the top of the card."""
    valid_to = node.valid_to.date().isoformat() if node.valid_to else "current"
    panel = Panel(
        Text(
            f"  kind: {node.kind}    name: {node.name}\n"
            f"  range: {node.file_path}:{node.line_start}-{node.line_end}\n"
            f"  language: {node.language}\n"
            f"  valid: {node.valid_from.date().isoformat()} → {valid_to}\n"
            f"  commit: {node.commit_sha or 'n/a'}",
            style="cyan",
        ),
        title="[bold]Matched CodeNode[/]",
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(panel)


def build_decision_panel(decision: Decision, file_path: str, line: int) -> Panel:
    """Render one decision as a Rich Panel card."""
    body = Text()
    body.append("[Location]\n", style="bold cyan")
    body.append(f"  {file_path}:{line}\n")
    body.append("[Decision]\n", style="bold yellow")
    body.append(f"  {decision.content}\n")
    body.append("[Reason]\n", style="bold yellow")
    body.append(f"  {decision.reason or '(not recorded)'}\n")
    body.append("[Alternatives]\n", style="bold yellow")
    if decision.alternatives:
        for item in decision.alternatives:
            body.append(f"  · {item}\n")
    else:
        body.append("  (none)\n")
    body.append("[Source]\n", style="bold yellow")
    body.append(f"  {decision.source.value} · {decision.source_ref}\n")
    body.append(
        f"  author: {decision.author or 'unknown'} · "
        f"date: {decision.timestamp.date().isoformat()}\n"
    )
    body.append("[Status]\n", style="bold yellow")
    body.append(f"  {format_status_label(decision.status.value)}\n")
    body.append("[Constraints]\n", style="bold yellow")
    if decision.constraints:
        for item in decision.constraints:
            body.append(f"  · {item}\n")
    else:
        body.append("  (none)\n")
    body.append("[Confidence]\n", style="bold yellow")
    body.append(f"  {format_confidence(decision.confidence)}\n")
    return Panel(
        body,
        title=f"[bold]Decision {decision.uid[:24]}[/]",
        border_style="yellow",
        padding=(1, 2),
    )


def render_decision_card(file_path: str, line: int, decisions: list[Decision]) -> None:
    """Render decision cards for a location."""
    console.print(
        f"[bold cyan]Query[/] {file_path}:{line} → [bold]{len(decisions)}[/] matched decision(s)\n"
    )
    for decision in decisions[:5]:
        console.print(build_decision_panel(decision, file_path, line))


def render_not_found(file_path: str, line: int | None = None) -> None:
    """Render the empty-result hint."""
    location = f"{file_path}:{line}" if line is not None else file_path
    console.print("[bold yellow]No decision record found[/]")
    console.print(f"[dim]No Decision bound to {location}. Try:[/]")
    console.print("[dim]  codegraph index <repo> --depth 50   # build the graph first[/]")
    console.print("[dim]  codegraph decisions --file <path> --timeline[/]")


def load_code_node_dgraph(file_path: str, line: int) -> CodeNode | None:
    """Load covering CodeNode from Dgraph."""
    from codegraph.graph import DgraphClient, DgraphConnectionError

    try:
        client = DgraphClient()
        if not client.ping():
            console.print(
                "[bold red]Dgraph connection failed[/] Cannot reach alpha. "
                "Run docker compose up -d first."
            )
            raise typer.Exit(code=3)
        node = client.query_node_at(file_path, line)
        client.close()
    except DgraphConnectionError as exc:
        console.print(f"[bold red]Dgraph connection failed[/] {exc}")
        raise typer.Exit(code=3) from exc

    if not node:
        return None
    return CodeNode(
        uid=str(node.get("node_uid") or node.get("uid") or ""),
        kind=str(node.get("kind") or ""),
        name=str(node.get("name") or ""),
        file_path=str(node.get("file_path") or ""),
        line_start=int(node.get("line_start") or 1),
        line_end=int(node.get("line_end") or 1),
        language=str(node.get("language") or ""),
        parent_uid=node.get("parent_uid") or None,
    )


def _load_decisions_dgraph(file_path: str, line: int) -> list[Decision]:
    """Load decisions from Dgraph for file:line."""
    from codegraph.graph import DgraphClient, DgraphConnectionError

    try:
        client = DgraphClient()
        if not client.ping():
            console.print(
                "[bold red]Dgraph connection failed[/] Cannot reach alpha. "
                "Run docker compose up -d first."
            )
            raise typer.Exit(code=3)
        raw_list = client.query_decisions_for(file_path, line)
        client.close()
    except DgraphConnectionError as exc:
        console.print(f"[bold red]Dgraph connection failed[/] {exc}")
        raise typer.Exit(code=3) from exc

    if raw_list:
        return [decision_from_dgraph(item) for item in raw_list]
    return load_decisions_sqlite(file_path, line)


def why_command(
    location: str,
    backend: str = typer.Option(
        "sqlite",
        "--backend",
        help="Graph backend: sqlite | dgraph",
        metavar="BACKEND",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of Rich cards",
    ),
) -> None:
    """Query decision cards for a source location.

    Args:
        location: Location string like `src/auth/session.ts:42`.
        backend: Storage backend, sqlite (default) or dgraph.
        as_json: Output JSON for editor extensions.
    """
    import json as jsonlib

    try:
        file_path, line = parse_location(location)
    except LocationError as exc:
        if as_json:
            typer.echo(jsonlib.dumps({"error": str(exc)}))
        else:
            console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    if backend not in {"sqlite", "dgraph"}:
        msg = f"Unknown backend: {backend} (use sqlite | dgraph)"
        if as_json:
            typer.echo(jsonlib.dumps({"error": msg}))
        else:
            console.print(f"[bold red]Invalid argument[/] {msg}")
        raise typer.Exit(code=2)

    if backend == "dgraph":
        node = load_code_node_dgraph(file_path, line)
        decisions = _load_decisions_dgraph(file_path, line)
    else:
        node = load_code_node_sqlite(file_path, line)
        decisions = load_decisions_sqlite(
            file_path, line, commit_sha=node.commit_sha if node else ""
        )

    if as_json:
        payload = {
            "file": file_path,
            "line": line,
            "node": _node_payload(node),
            "decisions": [_decision_payload(d) for d in decisions[:10]],
        }
        typer.echo(jsonlib.dumps(payload, ensure_ascii=False, indent=2))
        if not decisions:
            raise typer.Exit(code=1)
        return

    if node is not None:
        render_code_node_header(node)

    if not decisions:
        render_not_found(file_path, line)
        raise typer.Exit(code=1)

    render_decision_card(file_path, line, decisions)


def _node_payload(node: CodeNode | None) -> dict | None:
    """Serialize a CodeNode for --json."""
    if node is None:
        return None
    return {
        "uid": node.uid,
        "kind": node.kind,
        "name": node.name,
        "file_path": node.file_path,
        "line_start": node.line_start,
        "line_end": node.line_end,
        "language": node.language,
        "commit_sha": node.commit_sha,
    }


def _decision_payload(decision: Decision) -> dict:
    """Serialize a Decision for --json."""
    return {
        "uid": decision.uid,
        "content": decision.content,
        "reason": decision.reason,
        "alternatives": decision.alternatives,
        "status": decision.status.value,
        "source": decision.source.value,
        "source_ref": decision.source_ref,
        "timestamp": decision.timestamp.isoformat(),
        "author": decision.author,
        "file_path": decision.file_path,
        "line": decision.line,
        "constraints": decision.constraints,
        "confidence": decision.confidence,
    }


def decisions_command(
    file: str = typer.Option(..., "--file", help="File path", metavar="PATH"),
    timeline: bool = typer.Option(False, "--timeline", help="Show oldest-first evolution"),
) -> None:
    """List the decision evolution timeline for a file.

    Args:
        file: Target file path.
        timeline: Emit oldest-first when true.
    """
    rows = load_decisions_sqlite(file, 0)
    if not rows:
        rows = find_decisions_for_file(file)
    prefix = normalize_location_path(file)
    specific = [d for d in rows if d.file_path == prefix or d.file_path.startswith(prefix)]
    if not specific:
        # Fall back to any extracted decision so the timeline is still useful.
        from codegraph.storage import query_all_decisions

        db_path = db_path_for_root(Path.cwd())
        if db_path.exists():
            conn = connect(db_path)
            try:
                specific = query_all_decisions(conn)
            finally:
                conn.close()
    rows = specific or rows
    if not rows:
        render_not_found(file)
        raise typer.Exit(code=1)

    table = Table(title=f"Decision evolution · {file}")
    table.add_column("Date", style="cyan")
    table.add_column("Status")
    table.add_column("Decision", overflow="fold")
    table.add_column("Source", style="dim")
    ordered = list(rows) if timeline else list(reversed(rows))
    for decision in ordered[:15]:
        table.add_row(
            decision.timestamp.date().isoformat(),
            decision.status.value,
            decision.content,
            decision.source_ref,
        )
    console.print(table)


app = typer.Typer(help="Decision provenance for a source line")

if __name__ == "__main__":
    app()
