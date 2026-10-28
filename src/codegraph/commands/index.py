"""codegraph index: parse sources across Git history and persist the graph."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from codegraph.decisions.sources import extract_all
from codegraph.git.diff import get_changed_lines
from codegraph.git.history import CommitInfo, GitHistory
from codegraph.models import (
    CodeNode,
    Decision,
    DecisionTier,
    Edge,
    normalize_location_path,
)
from codegraph.parser.base import BaseParser
from codegraph.parser.registry import get_parser_for_path, is_supported_source
from codegraph.storage import (
    clear_graph,
    connect,
    count_decisions,
    count_edges,
    count_nodes,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    insert_decisions,
    insert_edges,
    insert_nodes,
    load_edges,
    load_nodes,
    replace_graph_rows,
)

console = Console()
logger = logging.getLogger(__name__)

MAX_CHANGED_LINES = 1000  # skip line-binding on huge diffs

# A decision that claims thousands of lines is not a line-level fact.
MAX_BINDING_FILES = 10
MAX_BINDING_LINES = 250

# Governed (ADR-style) binding stays deliberately small.
MAX_GOVERNED_FILES = 12
MAX_GOVERNED_NODES_PER_FILE = 60
MAX_GOVERNED_NODES = 200

GOVERNS_FRONT_MATTER = re.compile(r"^\s*governs\s*:\s*(?P<paths>.+)$", re.IGNORECASE | re.MULTILINE)
GOVERNS_COMMENT = re.compile(
    r"<!--\s*governs?\s*:\s*(?P<paths>.*?)\s*-->", re.IGNORECASE | re.DOTALL
)
BACKTICKED_PATH = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|js|mjs|cjs|java|go|rs|cpp|cc|cxx|hpp|hh|hxx|h))`"
)
BACKTICKED_IDENT = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")


def is_distinctive_identifier(ident: str) -> bool:
    """True when a backticked word is specific enough to identify code.

    Stops prose words like `index` or `decision` from binding an ADR to random
    symbols.
    """
    if len(ident) < 6:
        return False
    return "_" in ident or ident[0].isupper() or len(ident) >= 10

SKIP_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".codegraph",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    ".cargo",
    "vendor",
}

INDEX_STEPS: list[str] = [
    "Walk Git history",
    "Parse snapshots with tree-sitter",
    "Extract decisions from commits/ADRs",
    "Write graph store",
]


def resolve_repo_path(path: Path) -> Path:
    """Resolve and validate the repository path."""
    target = path.expanduser().resolve()
    if not target.exists():
        raise typer.BadParameter(f"Path not found: {path}")
    return target


def is_skipped_path(root: Path, file_path: str) -> bool:
    """Return True when a repo-relative path should be ignored."""
    parts = Path(file_path).parts
    return any(part in SKIP_DIRS for part in parts)


def parse_source_text(path_str: str, text: str) -> tuple[list[CodeNode], list[Edge]]:
    """Parse in-memory source text into nodes and edges."""
    parser = get_parser_for_path(Path(path_str))
    if parser is None:
        return [], []
    # Tree-sitter parsers read from disk; use a side channel via monkeypatch-like temp parse.
    nodes = parser.parse_text(path_str, text) if hasattr(parser, "parse_text") else []
    edges = parser.extract_edges(nodes) if nodes else []
    return nodes, edges


def _node_source(text: str, node: CodeNode) -> str:
    """Return the source lines a node version covers."""
    lines = text.splitlines()
    return "\n".join(lines[node.line_start - 1 : node.line_end])


def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware datetime so versions can be compared."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _has_unchanged_live_version(
    versions: list[CodeNode],
    node: CodeNode,
    text: str,
    history,
    rel_path: str,
    text_cache: dict[tuple[str, str], str],
    commit_timestamp: datetime | None = None,
) -> bool:
    """True when this commit must not open a new version of the symbol.

    Two cases:

    * a live version already covers the same range *and* the same source text, so
      the symbol did not change;
    * a live version was created by a **later** commit. This happens when history
      is re-read after an amend, rebase or reset, and the stored graph is already
      newer than the commit being ingested. Opening a version for the older
      commit would close the newer one at an earlier instant and invert the
      timeline.
    """
    for prev in versions:
        if prev.valid_to is not None:
            continue
        if commit_timestamp is not None and _as_utc(prev.valid_from) > _as_utc(
            commit_timestamp
        ):
            return True
        if prev.line_start != node.line_start or prev.line_end != node.line_end:
            continue
        if prev.commit_sha == node.commit_sha:
            return True
        cache_key = (prev.commit_sha, rel_path)
        prev_text = text_cache.get(cache_key)
        if prev_text is None:
            prev_text = history.get_file_at_commit(prev.commit_sha, rel_path)
            text_cache[cache_key] = prev_text
        if prev_text and _node_source(prev_text, prev) == _node_source(text, node):
            return True
    return False


def close_previous_versions(
    live: dict[tuple[str, str], list[CodeNode]],
    key: tuple[str, str],
    when: datetime,
) -> None:
    """Set valid_to on open node versions for a (file, name) key."""
    for node in live.get(key, []):
        if node.valid_to is None:
            node.valid_to = when


def _live_nodes(live: dict[tuple[str, str], list[CodeNode]]) -> list[CodeNode]:
    """Return every currently live node version."""
    return [
        node
        for versions in live.values()
        for node in versions
        if node.valid_to is None
    ]


def ingest_commit(
    history: GitHistory,
    commit: CommitInfo,
    live: dict[tuple[str, str], list[CodeNode]],
    all_nodes: list[CodeNode],
    all_edges: list[Edge],
    text_cache: dict[tuple[str, str], str] | None = None,
) -> None:
    """Parse changed source files at one commit and version nodes.

    Nodes are versioned first, then call edges are resolved against every symbol
    live at this commit — including symbols introduced by the same commit in
    another file. Resolving per file would drop cross-file calls, and the
    working-tree path already resolves them, so the two would disagree.
    """
    cache = text_cache if text_cache is not None else {}
    parsed: list[tuple[BaseParser, list[CodeNode]]] = []
    for rel in commit.changed_files:
        rel_n = normalize_location_path(rel)
        if is_skipped_path(history.root, rel_n) or not is_supported_source(Path(rel_n)):
            continue
        text = history.get_file_at_commit(commit.sha, rel_n)
        if not text:
            close_previous_versions(live, (rel_n, "*"), commit.timestamp)
            # close all nodes in that file
            for key in [k for k in live if k[0] == rel_n]:
                close_previous_versions(live, key, commit.timestamp)
            continue

        parser = get_parser_for_path(Path(rel_n))
        if parser is None:
            continue
        try:
            nodes = parser.parse_text(
                rel_n, text, commit_sha=commit.sha, valid_from=commit.timestamp
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parse failed at %s %s: %s", commit.sha[:10], rel_n, exc)
            continue

        seen_names = {(n.file_path, n.name) for n in nodes}
        for key in [k for k in live if k[0] == rel_n and (k[0], k[1]) not in seen_names]:
            close_previous_versions(live, key, commit.timestamp)

        for node in nodes:
            key = (node.file_path, node.name)
            if _has_unchanged_live_version(
                live.get(key, []), node, text, history, rel_n, cache, commit.timestamp
            ):
                # Same symbol, same lines, same source: keep the existing version
                # instead of forking a second live version.
                continue
            # Close every other live version of this symbol before appending.
            for prev in live.get(key, []):
                if prev.valid_to is None:
                    prev.valid_to = commit.timestamp
            live.setdefault(key, []).append(node)
            all_nodes.append(node)

        parsed.append((parser, nodes))

    live_scope = _live_nodes(live)
    for parser, nodes in parsed:
        try:
            all_edges.extend(parser.extract_edges(nodes, scope=live_scope))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Edge extract failed for %s: %s", nodes[0].file_path, exc)


def load_decisions(
    repo_path: Path,
    depth: int,
    use_llm: bool = False,
    llm_model: str = "llama3.2",
    progress_console: Console | None = None,
) -> list[Decision]:
    """Extract decisions from the repository's own history and documents.

    Nothing is fabricated: a repository whose commits and documents carry no
    rationale produces no decisions, and the index says so.

    Args:
        progress_console: Where human-readable output goes; defaults to stdout
            but is stderr when `--json` is in use so stdout stays parseable.
    """
    decisions = extract_all(
        repo_path, depth=depth, use_llm=use_llm, llm_model=llm_model
    )
    if not decisions:
        (progress_console or console).print(
            "[yellow]warn[/] No decisions found in commits, ADRs or CHANGELOG. "
            "The graph will hold structure only."
        )
        (progress_console or console).print(
            "[dim]Record why in a commit message ('... because ...'), an ADR, "
            "or a CHANGELOG entry, then re-run index.[/]"
        )
    return decisions


def _ingest_working_tree(
    root: Path, all_nodes: list[CodeNode], all_edges: list[Edge], jobs: int = 0
) -> None:
    """Parse files currently on disk when Git history is unavailable."""
    from codegraph.parser.parallel import parse_files_parallel
    from codegraph.parser.registry import is_supported_source

    now = datetime.now(timezone.utc)
    items: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_supported_source(path):
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        rel = normalize_location_path(str(path.relative_to(root)))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Read failed %s: %s", path, exc)
            continue
        items.append((rel, text))

    nodes, edges = parse_files_parallel(
        items, commit_sha="WORKTREE", valid_from=now, jobs=jobs
    )
    all_nodes.extend(nodes)
    all_edges.extend(edges)




def _commit_sha_from_ref(source_ref: str) -> str:
    """Extract a hex sha from a source_ref like 'commit abc123...'."""
    for token in source_ref.replace(":", " ").split():
        if len(token) >= 7 and all(c in "0123456789abcdefABCDEF" for c in token):
            return token
    return ""


def parse_governs(text: str) -> list[str]:
    """Return the code paths a document declares it governs.

    Two forms are recognised, so both MD/ADR conventions work:

    * a front-matter or inline line `governs: src/a.py, src/b/`
    * an HTML comment `<!-- governs: src/a.py -->`
    """
    out: list[str] = []
    for pattern in (GOVERNS_FRONT_MATTER, GOVERNS_COMMENT):
        for match in pattern.finditer(text or ""):
            for raw in re.split(r"[,\s]+", match.group("paths").strip()):
                value = normalize_location_path(raw).strip("`'\"*-")
                if value and value not in out:
                    out.append(value)
    return out


def _representative_nodes(nodes: list[CodeNode]) -> list[CodeNode]:
    """One node per (file, name), preferring the live version.

    Governed bindings must cover a whole file, not just its oldest symbols, so
    historical duplicates are collapsed before the fan-out cap is applied.
    """
    best: dict[tuple[str, str], CodeNode] = {}
    for node in nodes:
        key = (node.file_path, node.name)
        prev = best.get(key)
        if prev is None:
            best[key] = node
            continue
        prev_live, node_live = prev.valid_to is None, node.valid_to is None
        if node_live != prev_live:
            if node_live:
                best[key] = node
        elif _as_utc(node.valid_from) > _as_utc(prev.valid_from):
            best[key] = node
    return sorted(best.values(), key=lambda n: n.line_start)


def _governed_nodes(
    text: str,
    by_file: dict[str, list[CodeNode]],
    node_names: dict[str, list[CodeNode]],
) -> list[tuple[str, CodeNode]]:
    """Resolve the code a prose decision points at.

    Sources, in order of precision: an explicit `governs:` declaration, a
    backticked source path, and a backticked identifier that is a real node name.
    """
    targets: list[tuple[str, CodeNode]] = []
    seen: set[tuple[str, str]] = set()

    def add(path: str, node: CodeNode) -> None:
        key = (path, node.uid)
        if key not in seen:
            seen.add(key)
            targets.append((path, node))

    paths = parse_governs(text)
    paths += [normalize_location_path(p) for p in BACKTICKED_PATH.findall(text or "")]
    for value in paths:
        if len(targets) >= MAX_GOVERNED_NODES:
            break
        if value in by_file:
            for node in by_file[value][:MAX_GOVERNED_NODES_PER_FILE]:
                add(value, node)
            continue
        prefix = value.rstrip("/") + "/"
        matched = sorted(f for f in by_file if f.startswith(prefix))
        for file_path in matched[:MAX_GOVERNED_FILES]:
            if len(targets) >= MAX_GOVERNED_NODES:
                break
            for node in by_file[file_path][:MAX_GOVERNED_NODES_PER_FILE]:
                add(file_path, node)

    for ident in BACKTICKED_IDENT.findall(text or ""):
        if "." in ident or not is_distinctive_identifier(ident):
            continue
        candidates = node_names.get(ident, [])
        if not candidates or len({n.file_path for n in candidates}) > 3:
            continue  # too generic to be evidence about code
        for node in candidates[:MAX_GOVERNED_NODES_PER_FILE]:
            add(node.file_path, node)
    return targets


def _read_decision_text(root: Path, decision: Decision) -> str:
    """Read the document a prose decision came from, when it is a local file."""
    if not decision.file_path or not decision.file_path.endswith(".md"):
        return ""
    path = (root / decision.file_path).resolve()
    try:
        if path.is_file() and path.is_relative_to(root):
            return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""
    return ""


def cap_links(
    links: list[tuple[str, str, str, int]],
    *,
    max_files: int = MAX_BINDING_FILES,
    max_lines: int = MAX_BINDING_LINES,
) -> list[tuple[str, str, str, int]]:
    """Drop bindings that claim too much code to be a line-level fact.

    A commit that touched half the repository is provenance for a whole change,
    not evidence about a single line; such decisions stay reachable through the
    commit-level fallback instead of claiming hundreds of line links.
    """
    grouped: dict[str, list[tuple[str, str, str, int]]] = {}
    for item in links:
        grouped.setdefault(item[0], []).append(item)
    kept: list[tuple[str, str, str, int]] = []
    dropped = 0
    for decision_uid, items in grouped.items():
        files = {item[2] for item in items}
        if len(files) > max_files or len(items) > max_lines:
            dropped += 1
            logger.debug(
                "No line binding for %s: %s file(s), %s line(s)",
                decision_uid,
                len(files),
                len(items),
            )
            continue
        kept.extend(items)
    if dropped:
        logger.info("Kept commit-level binding for %s over-broad decision(s)", dropped)
    return kept


def bind_decisions_to_lines(
    root: Path,
    decisions: list[Decision],
    nodes: list[CodeNode],
) -> list[tuple[str, str, str, int]]:
    """Bind decisions to the code they describe.

    Commit decisions bind to the changed lines that fall inside a CodeNode.
    Decisions without a commit (ADRs, CHANGELOG entries) bind to the code they
    name: an explicit `governs:` declaration, a backticked source path, or a
    backticked identifier that matches a node name.

    Returns:
        Rows for decision_code_links: (decision_uid, node_uid, file_path, line).
    """
    links: list[tuple[str, str, str, int]] = []
    by_file: dict[str, list[CodeNode]] = {}
    for node in nodes:
        by_file.setdefault(node.file_path, []).append(node)

    governed_by_file = {path: _representative_nodes(items) for path, items in by_file.items()}
    governed_names: dict[str, list[CodeNode]] = {}
    for items in governed_by_file.values():
        for node in items:
            governed_names.setdefault(node.name, []).append(node)

    for decision in decisions:
        sha = _commit_sha_from_ref(decision.source_ref)
        if not sha:
            # Fall back to the decision's own file:line if present
            if decision.file_path and decision.line:
                matches = [
                    n
                    for n in by_file.get(decision.file_path, [])
                    if n.contains_line(decision.line)
                ]
                if matches:
                    node = min(matches, key=lambda n: n.line_end - n.line_start)
                    links.append((decision.uid, node.uid, decision.file_path, decision.line))
                continue
            if decision.tier is DecisionTier.DECISION:
                text = _read_decision_text(root, decision)
                haystack = "\n".join(
                    [decision.content, decision.reason, *decision.alternatives, text]
                )
                for path, node in _governed_nodes(haystack, governed_by_file, governed_names):
                    links.append((decision.uid, node.uid, path, node.line_start))
            continue

        try:
            changed = get_changed_lines(root, sha)
            total = sum(len(v) for v in changed.values())
            if total > MAX_CHANGED_LINES:
                # Keep binds only for lines that fall inside known CodeNodes.
                logger.warning(
                    "filtered line bind for %s: %s changed lines", sha, total
                )
                filtered: dict[str, list[int]] = {}
                for fpath, lines in changed.items():
                    hits = [
                        ln
                        for ln in lines
                        if any(n.contains_line(ln) for n in by_file.get(fpath, []))
                    ]
                    if hits:
                        filtered[fpath] = hits[:200]
                changed = filtered
        except Exception as exc:  # noqa: BLE001
            logger.warning("changed lines failed for %s: %s", sha, exc)
            changed = {}

        if not changed and decision.file_path and decision.line:
            matches = [
                n for n in by_file.get(decision.file_path, []) if n.contains_line(decision.line)
            ]
            if matches:
                node = min(matches, key=lambda n: n.line_end - n.line_start)
                links.append((decision.uid, node.uid, decision.file_path, decision.line))
            continue

        decision_links: list[tuple[str, str, str, int]] = []
        for file_path, lines in changed.items():
            candidates = by_file.get(file_path, [])
            for ln in lines:
                hit = [n for n in candidates if n.contains_line(ln)]
                if not hit:
                    continue
                node = min(hit, key=lambda n: n.line_end - n.line_start)
                decision_links.append((decision.uid, node.uid, file_path, ln))
        links.extend(cap_links(decision_links))
    return links


class GraphShrinkError(RuntimeError):
    """Raised when an incremental run would shrink the stored graph."""


def guard_node_collapse(new_count: int, previous_count: int, *, replace: bool) -> None:
    """Refuse an incremental write that would drop most of the stored graph.

    A full rebuild or a first index may legitimately produce any count; an
    incremental merge must never shrink the graph by more than half.

    Args:
        new_count: Node versions about to be written.
        previous_count: Node versions currently stored.
        replace: True when the write is a full rebuild.

    Raises:
        GraphShrinkError: When the write would lose data.
    """
    if replace or previous_count <= 0:
        return
    if new_count < previous_count * 0.5:
        raise GraphShrinkError(
            f"node count would drop from {previous_count} to {new_count}; "
            "this looks like a lost-history rebuild"
        )


def _close_superseded_live_versions(nodes: list[CodeNode]) -> int:
    """Repair a legacy graph that has several live versions of one symbol.

    Older `index` runs could leave two simultaneously-live versions of the same
    (file_path, name). Keep the newest and close the rest at its `valid_from`.

    Returns:
        Number of versions that were closed.
    """
    groups: dict[tuple[str, str], list[CodeNode]] = {}
    for node in nodes:
        if node.valid_to is None:
            groups.setdefault((node.file_path, node.name), []).append(node)
    closed = 0
    for versions in groups.values():
        if len(versions) < 2:
            continue
        versions.sort(key=lambda n: n.valid_from)
        keeper = versions[-1]
        for older in versions[:-1]:
            older.valid_to = keeper.valid_from
            closed += 1
    return closed


def _load_stored_graph(db_path: Path) -> tuple[list[CodeNode], list[Edge]]:
    """Load the persisted graph so an incremental run can merge into it."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        return load_nodes(conn), load_edges(conn)
    finally:
        conn.close()


def _is_flat_worktree_graph(nodes: list[CodeNode]) -> bool:
    """True when every stored node comes from a working-tree snapshot, not Git."""
    return all(node.commit_sha == "WORKTREE" for node in nodes)


def _recorded_node_count(root: Path) -> int:
    """Node versions the last successful index claimed to have written (0 if unknown)."""
    from codegraph.git.incremental import load_last_state

    value = load_last_state(root).get("node_count")
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def write_sqlite_graph(
    db_path: Path,
    nodes: list[CodeNode],
    edges: list[Edge],
    decisions: list[Decision],
    links: list[tuple[str, str, str, int]] | None = None,
    *,
    replace: bool = True,
) -> tuple[int, int, int]:
    """Persist nodes/edges/decisions/links and return counts.

    Args:
        db_path: SQLite database path.
        nodes: Node versions to store (full merged set when incremental).
        edges: Edges to store (full merged set when incremental).
        decisions: Decisions to store.
        links: decision_code_links rows.
        replace: True for a full rebuild (clears the tables first). False for an
            incremental run, where only the rows being rewritten are deleted.

    Returns:
        (node_count, edge_count, decision_count) after the write.
    """
    conn = connect(db_path)
    try:
        init_schema(conn)
        if replace:
            clear_graph(conn)
        else:
            replace_graph_rows(conn, [n.uid for n in nodes])
        node_uids = {n.uid for n in nodes}
        candidates = [e for e in edges if e.from_uid in node_uids and e.to_uid in node_uids]
        # Writing must be idempotent: re-reading history after an amend or rebase
        # re-derives edges that are already stored.
        unique_keys = dict.fromkeys(
            (e.from_uid, e.to_uid, e.kind, e.file_path, e.line) for e in candidates
        )
        live_edges = [
            Edge(from_uid=from_uid, to_uid=to_uid, kind=kind, file_path=path, line=line)
            for from_uid, to_uid, kind, path, line in unique_keys
        ]
        if len(live_edges) != len(edges):
            logger.debug(
                "Dropped %d duplicate or dangling edge(s)", len(edges) - len(live_edges)
            )
        insert_nodes(conn, nodes)
        insert_edges(conn, live_edges)
        insert_decisions(conn, decisions)
        insert_decision_links(conn, links or [])
        return count_nodes(conn), count_edges(conn), count_decisions(conn)
    finally:
        conn.close()


def run_index_progress(steps: list[str], progress_console: Console | None = None) -> None:
    """Show multi-stage index progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=progress_console or console,
    ) as progress:
        overall = progress.add_task("Indexing", total=len(steps))
        for step in steps:
            task = progress.add_task(step, total=6)
            for _ in range(6):
                progress.update(task, advance=1)
            progress.update(overall, advance=1)


def index_command(
    path: Path = typer.Argument(..., help="Repository or directory path to index", metavar="PATH"),
    depth: int = typer.Option(
        100,
        "--depth",
        help="How many recent commits to walk (default 100)",
        metavar="N",
    ),
    use_llm: bool = typer.Option(
        False,
        "--use-llm",
        help="Use local Ollama to extract decisions when rules miss",
    ),
    llm_model: str = typer.Option(
        "llama3.2",
        "--llm-model",
        help="Ollama model name for --use-llm",
        metavar="MODEL",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON summary",
    ),
    jobs: int = typer.Option(
        0,
        "--jobs",
        help="Parallel parse workers (0 = CPU-1)",
        metavar="N",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Force full rebuild (ignore incremental state)",
    ),
) -> None:
    """Parse Git history with tree-sitter and persist the code graph.

    Args:
        path: Repository root or subdirectory.
        depth: Max commits to walk.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    try:
        target = resolve_repo_path(path)
    except typer.BadParameter as exc:
        console.print(f"[bold red]Invalid argument[/] {exc}")
        raise typer.Exit(code=2) from exc

    root = target if target.is_dir() else target.parent
    # With --json the only thing on stdout must be the JSON document, so all
    # human-facing output goes to stderr.
    stream_console = Console(stderr=True) if as_json else console
    stream_console.print(
        f"[bold cyan]Indexing[/] {target} ... [dim]depth={depth}[/]"
    )
    run_index_progress(INDEX_STEPS, progress_console=stream_console)

    all_nodes: list[CodeNode] = []
    all_edges: list[Edge] = []
    live: dict[tuple[str, str], list[CodeNode]] = {}
    text_cache: dict[tuple[str, str], str] = {}
    commit_count = 0

    try:
        history = GitHistory(root)
    except ValueError as exc:
        stream_console.print(f"[yellow]warn[/] {exc}; parsing working tree only")
        history = None

    db_path = db_path_for_root(root)
    replace = full
    previous_nodes = 0
    previous_edges = 0
    if not full and db_path.exists():
        stored_nodes, stored_edges = _load_stored_graph(db_path)
        recorded = _recorded_node_count(root)
        if stored_nodes and history is not None and (
            _is_flat_worktree_graph(stored_nodes) or 0 < len(stored_nodes) < recorded
        ):
            stream_console.print(
                "[yellow]warn[/] stored graph is incomplete "
                f"({len(stored_nodes)} of {recorded or '?'} recorded node versions); "
                "rebuilding from scratch"
            )
            replace = True
        elif stored_nodes:
            replace = False
            previous_nodes = len(stored_nodes)
            previous_edges = len(stored_edges)
            repaired = _close_superseded_live_versions(stored_nodes)
            if repaired:
                stream_console.print(
                    f"[yellow]warn[/] repaired {repaired} duplicate live node version(s)"
                )
            all_nodes.extend(stored_nodes)
            all_edges.extend(stored_edges)
            for node in stored_nodes:
                if node.valid_to is None:
                    live.setdefault((node.file_path, node.name), []).append(node)
            stream_console.print(
                f"[dim]incremental[/] keeping {previous_nodes} stored node version(s), "
                f"{previous_edges} edge(s)"
            )

    head_sha = ""
    if history is not None:
        from codegraph.git.incremental import commits_after

        if full or replace:
            commits = list(history.iter_commits(depth=depth))
            pending = list(reversed(commits))
        else:
            pending = commits_after(root, history, depth=depth)
        for commit in pending:
            try:
                ingest_commit(history, commit, live, all_nodes, all_edges, text_cache)
                commit_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skip commit %s: %s", commit.sha, exc)
        try:
            head = next(history.iter_commits(depth=1), None)
            if head is not None:
                head_sha = head.sha
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot read HEAD: %s", exc)

    if not all_nodes:
        _ingest_working_tree(root, all_nodes, all_edges, jobs=jobs)

    if use_llm:
        stream_console.print(
            f"[yellow]warn[/] --use-llm enabled (model={llm_model}); "
            "falls back to rules if Ollama is down"
        )
    decisions = load_decisions(
        root, depth, use_llm=use_llm, llm_model=llm_model,
        progress_console=stream_console,
    )

    try:
        guard_node_collapse(len(all_nodes), previous_nodes, replace=replace)
    except GraphShrinkError as exc:
        stream_console.print(f"[bold red]Refusing to write[/] {exc}")
        stream_console.print(
            "[dim]Existing graph left untouched. Re-run with --full to rebuild "
            "from scratch.[/]"
        )
        raise typer.Exit(code=4) from exc
    links = bind_decisions_to_lines(root, decisions, all_nodes)
    node_count, edge_count, decision_count = write_sqlite_graph(
        db_path, all_nodes, all_edges, decisions, links, replace=replace
    )

    if head_sha:
        # Record the persisted size so a truncated graph is detected next run.
        from codegraph.git.incremental import save_last_head

        try:
            save_last_head(root, head_sha, node_count=node_count)
        except OSError as exc:  # noqa: BLE001
            logger.warning("Cannot save incremental state: %s", exc)

    if as_json:
        import json as jsonlib

        typer.echo(
            jsonlib.dumps(
                {
                    "root": str(root),
                    "commits": commit_count,
                    "nodes": node_count,
                    "edges": edge_count,
                    "decisions": decision_count,
                },
                ensure_ascii=False,
            )
        )
        return

    console.print()
    console.print(f"[bold green]Index complete[/]  [bold]{root}[/]")
    console.print(f"  · Commits walked: [bold]{commit_count}[/]")
    console.print(f"  · Nodes: [bold]{node_count}[/]")
    console.print(f"  · Edges: [bold]{edge_count}[/]")
    console.print(f"  · Decisions: [bold]{decision_count}[/]")
    console.print(f"  · Database: [bold]{db_path_for_root(root)}[/]")
    console.print("[dim]Next: codegraph why <file>:<line>  to view a decision card[/]")


app = typer.Typer(help="Index a codebase from Git history (tree-sitter + SQLite)")

if __name__ == "__main__":
    app()
