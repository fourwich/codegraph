"""codegraph why: decision provenance for a source location."""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codegraph.i18n import help_text, is_chinese, t
from codegraph.models import (
    CodeNode,
    Decision,
    decision_to_dict,
    node_to_dict,
    normalize_location_path,
    select_decisions,
)
from codegraph.storage import (
    connect,
    db_path_for_root,
    find_db,
    find_node_at_line,
    find_nodes_by_name,
    query_decisions_for_commit,
    query_decisions_for_dir,
    query_decisions_for_file,
    query_decisions_for_file_links,
    query_decisions_for_line,
    query_decisions_for_line_links,
    query_decisions_for_node_lines,
)
from codegraph.translate import MACHINE_MARK, Translator

_TRANSLATOR: Translator | None = None

console = Console()

LOCATION_RE = re.compile(r"^(?P<file>.+):(?P<line>\d+)$")


class LocationError(ValueError):
    """User-supplied file:line is invalid."""


def normalize_user_path(raw: str) -> str:
    """Normalize a user path, turning an absolute path inside the repo into a relative one.

    Editors such as the VS Code extension hand over `doc.uri.fsPath`, which is
    absolute; stored paths are repo-relative.

    The base has to be the repository root, not the current directory: after
    `find_db` locates a database above cwd, the caller may be anywhere, and an
    absolute path that is not under cwd would otherwise stay absolute
    (`D:/repo/src/a.py`), which never matches the stored `src/a.py`.
    """
    path = Path(raw)
    if not path.is_absolute():
        return normalize_location_path(raw)

    resolved = path.resolve()
    bases: list[Path] = []
    # The most reliable base is the database that owns the file being asked
    # about, found by walking up from the file itself. Falling back to cwd covers
    # the editor case, where the extension passes an absolute path inside the
    # workspace the user opened.
    file_db = find_db(resolved.parent)
    if file_db is not None:
        bases.append(file_db.parent.parent)  # <repo>/.codegraph/graph.db -> <repo>
    cwd_db = find_db()
    if cwd_db is not None:
        bases.append(cwd_db.parent.parent)
    bases.append(Path.cwd())
    for base in bases:
        try:
            return resolved.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return normalize_location_path(raw)


def parse_location(raw: str, root: Path | None = None) -> tuple[str, int]:
    """Parse `file:line`, or resolve a bare symbol name to its first definition.

    `path:line` remains the precise form. A caller that knows only the symbol — which
    is the common case when reading unfamiliar code, or when an agent is told "explain
    `insert_nodes`" — gets the innermost live definition instead of an error. Several
    symbols can share a name; the first candidate is used and its location is echoed,
    so the caller can see which one was chosen.

    Args:
        raw: Either `path:line`, or an exact symbol name.
        root: Repository root for a symbol lookup; defaults to the current directory.

    Returns:
        A repo-relative path and a 1-based line inside the matching symbol.

    Raises:
        LocationError: when the value is empty, malformed, or names nothing indexed.
    """
    value = raw.strip()
    if not value:
        raise LocationError("Location cannot be empty. Use the form src/main.py:42")

    match = LOCATION_RE.match(value)
    if not match:
        resolved = _resolve_symbol(value, root)
        if resolved is not None:
            return resolved
        hint = _near_miss_hint(value)
        raise LocationError(
            f"Cannot parse location '{raw}'. Expected path:line (src/main.py:42) "
            "or an indexed symbol name."
            + (f" Did you mean: {hint}?" if hint else "")
            + " Run `codegraph index .` first if the repository has no graph yet."
        )

    line_no = int(match.group("line"))
    if line_no < 1:
        raise LocationError(f"Line number must be >= 1, got: {line_no}")

    raw_file = match.group("file")
    # Remember the database that owns the *original* path before it becomes a
    # repo-relative string: `normalize_user_path` strips the absolute prefix, and
    # after that there is no way to tell which repository the user meant.
    _remember_db_for(raw_file)
    return normalize_user_path(raw_file), line_no


def _near_miss_hint(name: str, limit: int = 3) -> str:
    """Return up to `limit` indexed symbol names close to `name`, or an empty string.

    A substring match in either direction covers both mistakes that matter: a
    truncated name (`insert` for `insert_nodes`) and an over-qualified one
    (`storage.insert_nodes`). Case-insensitive, because the caller typed it from
    memory rather than from a listing.
    """
    db_path = _resolve_db(Path.cwd(), name)
    if not db_path.is_file():
        return ""
    needle = name.rsplit(".", 1)[-1].strip().lower()
    if len(needle) < 3:
        return ""
    try:
        conn = connect(db_path)
    except sqlite3.Error:
        return ""
    try:
        rows = conn.execute(
            "SELECT DISTINCT name FROM nodes WHERE (valid_to IS NULL OR valid_to >= ?) "
            "AND (lower(name) LIKE ? OR ? LIKE '%' || lower(name) || '%') "
            "AND length(name) >= 3 "
            # A name the query starts with is what the caller meant; a name that merely
            # contains the query is a weaker guess.
            "ORDER BY (lower(name) LIKE ?) DESC, abs(length(name) - ?) ASC, name "
            "LIMIT ?",
            (
                datetime.now(timezone.utc).isoformat(),
                f"%{needle}%",
                needle,
                f"{needle}%",
                len(needle),
                limit,
            ),
        ).fetchall()
    finally:
        conn.close()
    return ", ".join(row[0] for row in rows if row[0])


def _resolve_symbol(name: str, root: Path | None = None) -> tuple[str, int] | None:
    """Turn an exact symbol name into (path, first line), or None when unknown."""
    # Same resolution as a `path:line` query, so the two forms find the same database
    # no matter which directory the caller is in.
    db_path = _resolve_db(root or Path.cwd(), name)
    if not db_path.is_file():
        return None
    try:
        conn = connect(db_path)
    except sqlite3.Error:
        return None
    try:
        nodes = find_nodes_by_name(conn, name, limit=1)
    finally:
        conn.close()
    if not nodes:
        return None

    # A `path:line` query records the owning database before relativising the path; the
    # symbol branch must do the same, or the later decision lookup reads a different
    # database and reports no record for a line that has one.
    global _QUERY_DB
    _QUERY_DB = db_path

    node = nodes[0]
    return node.file_path, node.line_start



def _level_key(level: str) -> str:
    """Map a `binding` value to its query-summary message key.

    The value itself stays English in JSON; only the sentence that mentions it is
    translated.
    """
    return level if level in {"line", "file", "dir", "commit"} else "line"

def _current_stdout_encodes(text: str) -> bool:
    """True when the active stdout encoding can represent text."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def format_status_label(status_value: str) -> str:
    """Map decision status to a short label, degrading to ASCII when needed.

    Three axes vary independently: the status word (translated), the symbol (only when
    the console can encode it), and the ASCII fallback for consoles that cannot. The
    status value itself stays English everywhere else, so a script reading JSON sees the
    same token in every locale.
    """
    symbols = {
        "accepted": "✅",
        "superseded": "🔁",
        "rejected": "⛔",
    }
    keys = {
        "accepted": "status.active",
        "superseded": "status.superseded",
        "rejected": "status.rejected",
    }
    key = keys.get(status_value)
    word = t(key) if key is not None else status_value
    symbol = symbols.get(status_value, "")

    if symbol and _current_stdout_encodes(f"{symbol} {word}"):
        return f"{symbol} {word}"
    if _current_stdout_encodes(word):
        return word
    # A console that cannot encode the translation falls back to the English token.
    return status_value.upper()


def format_confidence(confidence: float) -> str:
    """Format 0-1 confidence as stars and percent."""
    percent = int(round(confidence * 100))
    stars = "★" * int(round(confidence * 5)) + "☆" * (5 - int(round(confidence * 5)))
    return f"{stars}  {percent}%"


# Database resolved from the location the user actually typed, set by
# `_remember_db_for` during argument parsing. `None` means "fall back to cwd".
_QUERY_DB: Path | None = None


def _remember_db_for(raw_path: str) -> None:
    """Record which graph database owns `raw_path`, before it is relativised.

    Needed because a user may run `codegraph index some/repo` and then query an
    absolute path inside it from an unrelated directory; the database lives in
    `some/repo`, not in cwd.
    """
    global _QUERY_DB
    _QUERY_DB = None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        return
    found = find_db(candidate.parent)
    if found is not None:
        _QUERY_DB = found


def _resolve_db(root: Path | None = None, file_path: str = "") -> Path:
    """Locate the graph database for a query.

    Priority order matters for the case that actually breaks: a user runs
    `codegraph index some/repo` from elsewhere, then asks about a file inside
    that repo. `index` wrote the database into `some/repo`, so looking only at the
    current directory reports "no record" for everything.

    1. the database resolved from the location the user typed;
    2. walk up from the file being asked about — the most reliable clue;
    3. walk up from cwd;
    4. fall back to `<cwd>/.codegraph/graph.db`, which is where `index` writes
       when given no path.
    """
    if _QUERY_DB is not None and _QUERY_DB.is_file():
        return _QUERY_DB

    if file_path:
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = (root or Path.cwd()) / candidate
        found = find_db(candidate.parent if candidate.suffix else candidate)
        if found is not None:
            return found

    base = root or Path.cwd()
    found = find_db(base)
    return found if found is not None else db_path_for_root(base)


def load_code_node_sqlite(file_path: str, line: int, root: Path | None = None) -> CodeNode | None:
    """Load covering CodeNode from SQLite if an index exists."""
    db_path = _resolve_db(root, file_path)
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
    file_path: str,
    line: int,
    root: Path | None = None,
    commit_sha: str = "",
) -> tuple[list[Decision], str]:
    """Load decisions with line → file → commit → directory fallback.

    Returns:
        (decisions, level) where level is "line", "file", "commit", or "dir".
    """
    db_path = _resolve_db(root, file_path)
    rows: list[Decision] = []
    level = "line"
    if db_path.exists():
        try:
            conn = connect(db_path)
        except sqlite3.Error as exc:
            console.print(f"[yellow]warn[/] Cannot open graph database {db_path}: {exc}")
            return [], "none"
        try:
            # A line-level record is any record linked to the symbol that covers
            # this line. Querying the node range first stops an unrelated
            # exact-line commit record from shadowing it.
            covering = find_node_at_line(conn, file_path, line)
            if covering is not None:
                rows = query_decisions_for_node_lines(
                    conn, file_path, covering.line_start, covering.line_end
                )
                if rows:
                    level = "line"
            if not rows:
                rows = query_decisions_for_line_links(conn, file_path, line)
                if rows:
                    level = "line"
            if not rows:
                rows = query_decisions_for_line(conn, file_path, line)
            if not rows:
                rows = query_decisions_for_file(conn, file_path)
                level = "file"
            if not rows and commit_sha:
                rows = query_decisions_for_commit(conn, commit_sha)
                level = "commit"
            if not rows:
                rows = query_decisions_for_dir(conn, file_path, limit=5)
                level = "dir"
        finally:
            conn.close()
    if rows:
        return rows, level
    return [], "none"


def _parse_ts(value: object) -> datetime:
    """Parse an ISO timestamp or fall back to now."""
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _load_all_decisions() -> list[Decision]:
    """Load every decision from the local graph database, if it exists."""
    from codegraph.storage import query_all_decisions

    db_path = db_path_for_root(Path.cwd())
    if not db_path.exists():
        return []
    conn = connect(db_path)
    try:
        return query_all_decisions(conn)
    finally:
        conn.close()


def render_code_node_header(node: CodeNode) -> None:
    """Render the hit CodeNode summary at the top of the card."""
    valid_to = (
        node.valid_to.date().isoformat() if node.valid_to else t("node.current")
    )
    panel = Panel(
        Text(
            f"  {t('node.kind')}: {node.kind}    {t('node.name')}: {node.name}\n"
            f"  {t('node.range')}: {node.file_path}:{node.line_start}-{node.line_end}\n"
            f"  {t('node.language')}: {node.language}\n"
            f"  {t('node.valid')}: {node.valid_from.date().isoformat()} → {valid_to}\n"
            f"  {t('node.commit')}: {node.commit_sha or t('node.na')}",
            style="cyan",
        ),
        title=f"[bold]{t('card.matched_node')}[/]",
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(panel)


def decision_title(decision: Decision, index: int = 1) -> str:
    """Build a human-readable panel title (never leak internal uids)."""
    snippet = " ".join((decision.content or "").split())
    if snippet:
        snippet = snippet[:40] + ("…" if len(snippet) > 40 else "")
        return f"{t('card.decision')} #{index}: {snippet}"
    ref = (decision.source_ref or "").split()[-1] if decision.source_ref else ""
    return f"Decision #{index}" + (f" · {ref}" if ref else "")


def _append_translation(body: Text, original: str) -> None:
    """Append a machine translation beneath `original`, or nothing.

    The original is the record and stays authoritative. A translation is prefixed and
    dimmed so a reader can see at a glance that these are not the project's words; when
    no local model is available nothing is appended, which is the honest outcome.
    """
    if not is_chinese() or not original.strip():
        return
    translated = _translator().translate(original)
    if not translated:
        return
    body.append(f"  [dim]{MACHINE_MARK}：{translated}[/]\n")


def _translator() -> Translator:
    """Return the process-wide translator, honouring `CODEGRAPH_TRANSLATE_MODEL`."""
    global _TRANSLATOR
    if _TRANSLATOR is None:
        model = os.environ.get("CODEGRAPH_TRANSLATE_MODEL", "qwen2.5:3b").strip()
        _TRANSLATOR = Translator(model=model or "qwen2.5:3b")
    return _TRANSLATOR


def build_decision_panel(
    decision: Decision, file_path: str, line: int, level: str = "line", index: int = 1
) -> Panel:
    """Render one decision as a Rich Panel card."""
    body = Text()
    body.append(f"[{t('card.location')}]\n", style="bold cyan")
    body.append(f"  {file_path}:{line}\n")
    if level in {"file", "commit", "dir"}:
        body.append(
            f"  binding: {t(f'query.{_level_key(level)}')}\n", style="dim"
        )
    body.append(f"[{t('card.decision')}]\n", style="bold yellow")
    body.append(f"  {decision.content}\n")
    _append_translation(body, decision.content)
    body.append(f"[{t('card.reason')}]\n", style="bold yellow")
    reason = (decision.reason or "").strip()
    if not reason or reason == decision.content:
        body.append(f"  {t('card.not_recorded')}\n")
    else:
        body.append(f"  {reason}\n")
        _append_translation(body, reason)
    body.append(f"[{t('card.alternatives')}]\n", style="bold yellow")
    if decision.alternatives:
        for item in decision.alternatives:
            body.append(f"  · {item}\n")
    else:
        body.append(f"  {t('card.none')}\n")
    body.append(f"[{t('card.source')}]\n", style="bold yellow")
    body.append(f"  {decision.source.value} · {decision.source_ref}\n")
    body.append(
        f"  author: {decision.author or 'unknown'} · "
        f"date: {decision.timestamp.date().isoformat()}\n"
    )
    body.append(f"[{t('card.status')}]\n", style="bold yellow")
    body.append(f"  {format_status_label(decision.status.value)}\n")
    body.append(f"[{t('card.constraints')}]\n", style="bold yellow")
    if decision.constraints:
        for item in decision.constraints:
            body.append(f"  · {item}\n")
    else:
        body.append("  (none)\n")
    body.append("[Confidence]\n", style="bold yellow")
    body.append(f"  {format_confidence(decision.confidence)}\n")
    return Panel(
        body,
        title=f"[bold]{decision_title(decision, index)}[/]",
        border_style="yellow",
        padding=(1, 2),
    )


def render_decision_card(
    file_path: str, line: int, decisions: list[Decision], level: str = "line"
) -> None:
    """Render decision cards for a location.

    Args:
        file_path: Queried file.
        line: Queried line.
        decisions: Decisions to show.
        level: Binding strength — line / file / commit / dir / none.
    """
    # The sentence is prose, so it is translated; `level` itself stays an English
    # binding value everywhere else (JSON, the card header).
    tag = t(f"query.{_level_key(level)}")
    console.print(
        f"[bold cyan]{t('query.label')}[/] {file_path}:{line} → "
        f"[bold]{len(decisions)}[/] {tag}\n"
    )
    for i, decision in enumerate(decisions[:5], start=1):
        panel = build_decision_panel(decision, file_path, line, level=level, index=i)
        console.print(panel)


def render_not_found(
    file_path: str,
    line: int | None = None,
    hidden_records: int = 0,
    related: list[Decision] | None = None,
) -> None:
    """Render the empty-result hint.

    Args:
        file_path: Queried file.
        line: Queried line, when known.
        hidden_records: Records that exist but were filtered out by the tier
            and category defaults.
        related: Decisions bound to this file but not to this line. Showing them
            turns "nothing here" into an answer for files governed by an ADR.
    """
    location = f"{file_path}:{line}" if line is not None else file_path
    console.print(f"[bold yellow]{t('empty.no_decision')}[/]")
    if related:
        console.print("[dim]No record is tied to this line, but this file is governed by:[/]")
        for item in related:
            text = item.content if len(item.content) <= 74 else item.content[:71] + "..."
            console.print(f"  [cyan]{text}[/]")
            console.print(f"[dim]    source: {item.source_ref}[/]")
        console.print("[dim]  codegraph decisions --timeline   # all decisions[/]")
        return
    if hidden_records:
        console.print(
            f"[dim]{hidden_records} history record(s) exist for {location} "
            "but are not decisions.[/]"
        )
        console.print("[dim]  Add --include-events (and --include-dependency) to see them.[/]")
        return
    console.print(f"[dim]No Decision bound to {location}. Try:[/]")
    console.print("[dim]  codegraph index <repo> --depth 50   # build the graph first[/]")
    console.print("[dim]  codegraph decisions --file <path> --timeline[/]")


def _file_governed_decisions(
    file_path: str, include_events: bool, include_dependency: bool
) -> list[Decision]:
    """Decisions bound to this file by a link, for an otherwise empty result."""
    db_path = db_path_for_root(Path.cwd())
    if not db_path.exists():
        return []
    try:
        conn = connect(db_path)
        try:
            rows = query_decisions_for_file_links(conn, file_path)
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return []
    return select_decisions(
        rows, include_events=include_events, include_dependency=include_dependency
    )[:2]


def why_command(
    location: str,
    as_json: bool = typer.Option(
        False,
        "--json",
        help=help_text("Emit machine-readable JSON instead of Rich cards", "输出 JSON 而非卡片"),
    ),
    include_dependency: bool = typer.Option(
        False,
        "--include-dependency",
        help=help_text("Include dependency bumps (hidden)", "含依赖升级（默认隐藏）"),
    ),
    include_events: bool = typer.Option(
        False,
        "--include-events",
        help=help_text(
            "Include event records (plain history: commit subjects, changelog lines)",
            "包含事件记录（纯历史：提交标题、变更日志行）",
        ),
    ),
    root: str = typer.Option(
        "",
        "--root",
        help=help_text(
            "Repository root; needed to query a symbol from outside its repo",
            "仓库根目录；在仓库外按符号查询时指定",
        ),
    ),
) -> None:
    """Query decision cards for a source location.

    Args:
        location: Location string like `src/auth/session.ts:42`.
        as_json: Output JSON for editor extensions.
    """
    import json as jsonlib

    try:
        file_path, line = parse_location(location, root=Path(root).resolve() if root else None)
    except LocationError as exc:
        if as_json:
            typer.echo(jsonlib.dumps({"error": str(exc)}))
        else:
            console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    node = load_code_node_sqlite(file_path, line)
    raw_decisions, level = load_decisions_sqlite(
        file_path, line, commit_sha=node.commit_sha if node else ""
    )
    decisions = select_decisions(
        raw_decisions,
        include_events=include_events,
        include_dependency=include_dependency,
    )
    hidden_records = max(len(raw_decisions) - len(decisions), 0)
    governed = [] if decisions else _file_governed_decisions(
        file_path, include_events, include_dependency
    )

    if as_json:
        payload = {
            "file": file_path,
            "line": line,
            "node": _node_payload(node),
            "decisions": [_decision_payload(d) for d in decisions[:10]],
            "binding": level,
            "related": [_decision_payload(d) for d in governed],
        }
        typer.echo(jsonlib.dumps(payload, ensure_ascii=False, indent=2))
        if not decisions:
            raise typer.Exit(code=1)
        return

    if node is not None and level != "line":
        try:
            db_path = db_path_for_root(Path.cwd())
            if db_path.exists():
                conn = connect(db_path)
                try:
                    near = query_decisions_for_node_lines(
                        conn, file_path, node.line_start, node.line_end
                    )
                finally:
                    conn.close()
            else:
                near = []
        except Exception:  # noqa: BLE001
            near = []
        if near:
            near_visible = select_decisions(
                near,
                include_events=include_events,
                include_dependency=include_dependency,
            )
            hidden_records += len(near) - len(near_visible)
            if near_visible:
                decisions = near_visible
                level = "line"

    if node is not None:
        render_code_node_header(node)
    else:
        console.print(
            "[dim]No active code node covers this line "
            "(the symbol may have moved or been removed).[/]"
        )

    if not decisions:
        render_not_found(file_path, line, hidden_records=hidden_records, related=governed)
        raise typer.Exit(code=1)

    render_decision_card(file_path, line, decisions, level=level)


def _node_payload(node: CodeNode | None) -> dict | None:
    """Serialize a CodeNode for --json."""
    return node_to_dict(node) if node is not None else None


def _decision_payload(decision: Decision) -> dict:
    """Serialize a Decision for --json."""
    return decision_to_dict(decision)


def decisions_command(
    file: str = typer.Option(
        "",
        "--file",
        help="File path (omit to list decisions for every file)",
        metavar="PATH",
    ),
    timeline: bool = typer.Option(False, "--timeline", help="Show oldest-first evolution"),
    include_dependency: bool = typer.Option(
        False,
        "--include-dependency",
        help="Include dependency-bump decisions (hidden by default)",
    ),
    include_events: bool = typer.Option(
        False,
        "--include-events",
        help="Include event records (plain history: commit subjects, changelog lines)",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of a table",
    ),
) -> None:
    """List the decision evolution timeline, for one file or for everything.

    Args:
        file: Target file path; omitted means every file.
        timeline: Emit oldest-first when true.
        include_dependency: Show dependency-bump decisions too.
        include_events: Show event-tier records too.
        as_json: Emit JSON for editors and scripts.
    """
    prefix = normalize_location_path(file) if file else ""
    rows = [
        d
        for d in _load_all_decisions()
        if not prefix or d.file_path == prefix or d.file_path.startswith(prefix)
    ]
    filtered = select_decisions(
        rows,
        include_events=include_events,
        include_dependency=include_dependency,
    )
    if not filtered and not as_json:
        render_not_found(
            file or "this repository", hidden_records=max(len(rows) - len(filtered), 0)
        )
        raise typer.Exit(code=1)
    rows = filtered

    if as_json:
        import json as jsonlib

        ordered_json = list(rows) if timeline else list(reversed(rows))
        typer.echo(
            jsonlib.dumps(
                {
                    "file": file or None,
                    "count": len(ordered_json),
                    "decisions": [decision_to_dict(d) for d in ordered_json],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if not ordered_json:
            raise typer.Exit(code=1)
        return

    table = Table(title=f"Decision evolution · {file or 'all files'}")
    table.add_column("Date", style="cyan")
    table.add_column("Status")
    table.add_column("Decision", overflow="fold")
    table.add_column("Kind", style="dim")
    table.add_column("Source", style="dim")
    ordered = list(rows) if timeline else list(reversed(rows))
    for decision in ordered[:15]:
        table.add_row(
            decision.timestamp.date().isoformat(),
            decision.status.value,
            decision.content,
            decision.tier.value,
            decision.source_ref,
        )
    console.print(table)


app = typer.Typer(help="Decision provenance for a source line")

if __name__ == "__main__":
    app()
