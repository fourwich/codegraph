"""FastAPI app serving the CodeGraph web UI and JSON APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from codegraph.models import Decision, normalize_location_path, select_decisions
from codegraph.storage import (
    connect,
    count_edges_at,
    db_path_for_root,
    list_edges_at,
    query_all_decisions,
    query_decisions_for_file,
    query_nodes_at,
)

STATIC_DIR = Path(__file__).parent / "static"


def _sqlite_path() -> Path:
    return db_path_for_root(Path.cwd())


def _matches_scope(path: str, prefix: str) -> bool:
    """True when a path is the scope itself or lives under it."""
    if not prefix or prefix == ".":
        return True
    candidate = normalize_location_path(path or "")
    return bool(candidate) and (candidate == prefix or candidate.startswith(prefix + "/"))


def _governed_paths(conn) -> dict[str, set[str]]:
    """Map each decision to the code files it is bound to."""
    rows = conn.execute(
        "SELECT DISTINCT decision_uid, file_path FROM decision_code_links"
    ).fetchall()
    out: dict[str, set[str]] = {}
    for decision_uid, file_path in rows:
        out.setdefault(str(decision_uid), set()).add(str(file_path))
    return out


def _in_scope(decision: Decision, prefix: str, governed: dict[str, set[str]]) -> bool:
    """A decision is in scope when it was recorded there or governs code there."""
    if _matches_scope(decision.file_path, prefix):
        return True
    return any(_matches_scope(path, prefix) for path in governed.get(decision.uid, ()))


def _load_graph_sqlite(at: datetime, scope: str) -> dict[str, Any]:
    """Load nodes/edges/decisions valid at a timestamp, filtered by scope.

    The scope is never widened behind the caller's back: an empty result means
    "nothing in this scope", and the stats describe exactly what came back.
    """
    db_path = _sqlite_path()
    if not db_path.exists():
        return {"nodes": [], "edges": [], "decisions": [], "stats": _empty_stats(),
                "scope": normalize_location_path(scope) or "."}
    prefix = normalize_location_path(scope).rstrip("/")
    conn = connect(db_path)
    try:
        nodes = query_nodes_at(conn, at, prefix)
        edge_count = count_edges_at(conn, at, prefix)
        edges = list_edges_at(conn, at, prefix, limit=400)
        governed = _governed_paths(conn)
        decisions = [
            d
            for d in select_decisions(query_all_decisions(conn))
            if d.timestamp.date() <= at.date() and _in_scope(d, prefix, governed)
        ]
        return {
            "nodes": [_node_json(n) for n in nodes],
            "edges": edges,
            "decisions": [_decision_json(d) for d in decisions[:50]],
            "stats": {
                "nodes": len(nodes),
                "edges": edge_count,
                "decisions": len(decisions),
            },
            "scope": prefix or ".",
        }
    finally:
        conn.close()


def _empty_stats() -> dict[str, int]:
    return {"nodes": 0, "edges": 0, "decisions": 0}


def _node_json(node: Any) -> dict[str, Any]:
    valid_from = getattr(node, "valid_from", None)
    valid_to = getattr(node, "valid_to", None)
    return {
        "uid": node.uid,
        "kind": node.kind,
        "name": node.name,
        "file_path": node.file_path,
        "line_start": node.line_start,
        "line_end": node.line_end,
        "language": node.language,
        "commit_sha": getattr(node, "commit_sha", ""),
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_to": valid_to.isoformat() if valid_to else None,
    }


def _decision_json(decision: Decision) -> dict[str, Any]:
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
        "category": decision.category,
        "tier": decision.tier.value,
    }


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="CodeGraph", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        """Serve the single-page UI."""
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/static/{path:path}")
    def static_files(path: str) -> FileResponse:
        """Serve CSS/JS assets."""
        target = (STATIC_DIR / path).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())):
            raise HTTPException(status_code=404, detail="Not found")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(target)

    @app.get("/api/graph")
    def api_graph(
        at: str = Query(default=""),
        scope: str = Query(default="."),
    ) -> JSONResponse:
        """Return graph payload valid at a date."""
        return JSONResponse(_load_graph_sqlite(_parse_date(at), scope))

    @app.get("/api/why")
    def api_why(
        file: str = Query(...),
        line: int = Query(...),
    ) -> JSONResponse:
        """Return node + decisions for a file:line.

        Uses the same resolution as `codegraph why`, so the UI and the CLI
        cannot disagree about whether a decision exists for a line.
        """
        from codegraph.commands.why import load_code_node_sqlite, load_decisions_sqlite

        path = normalize_location_path(file)
        db_path = _sqlite_path()
        node = None
        decisions: list[Decision] = []
        level = "none"
        if db_path.exists():
            root = db_path.parent.parent
            found = load_code_node_sqlite(path, line, root=root)
            node = _node_json(found) if found else None
            rows, level = load_decisions_sqlite(
                path, line, root=root, commit_sha=found.commit_sha if found else ""
            )
            decisions = select_decisions(rows)
        return JSONResponse(
            {
                "file": path,
                "line": line,
                "node": node,
                "decisions": [_decision_json(d) for d in decisions[:10]],
                "binding": level,
            }
        )

    @app.get("/api/decisions")
    def api_decisions(
        file: str = Query(default=""),
    ) -> JSONResponse:
        """Return decision timeline for a file or all decisions."""
        db_path = _sqlite_path()
        decisions: list[Decision] = []
        if db_path.exists():
            conn = connect(db_path)
            try:
                decisions = (
                    query_decisions_for_file(conn, normalize_location_path(file))
                    if file
                    else query_all_decisions(conn)
                )
                decisions = select_decisions(decisions)
            finally:
                conn.close()
        return JSONResponse({"decisions": [_decision_json(d) for d in decisions]})

    @app.get("/api/timeline")
    def api_timeline(
        scope: str = Query(default="."),
    ) -> JSONResponse:
        """Return commit-ish date ticks for the time slider."""
        return JSONResponse({"ticks": _timeline_sqlite(scope)})

    return app


def _parse_date(raw: str) -> datetime:
    """Parse YYYY-MM-DD or default to now (end-of-day inclusive)."""
    value = (raw or "").strip()
    if not value:
        return datetime.now(timezone.utc)
    try:
        day = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {raw}") from exc
    # Use end-of-day so nodes stamped later the same day are included.
    return day.replace(hour=23, minute=59, second=59)


def _timeline_sqlite(scope: str) -> list[str]:
    """Return the distinct dates that have node versions inside the scope."""
    db_path = _sqlite_path()
    if not db_path.exists():
        return []
    prefix = normalize_location_path(scope).rstrip("/")
    conn = connect(db_path)
    try:
        if not prefix or prefix == ".":
            rows = conn.execute(
                "SELECT DISTINCT substr(valid_from, 1, 10) AS d FROM nodes "
                "WHERE valid_from IS NOT NULL ORDER BY d"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT substr(valid_from, 1, 10) AS d FROM nodes "
                "WHERE valid_from IS NOT NULL AND (file_path = ? OR file_path LIKE ?) "
                "ORDER BY d",
                (prefix, prefix + "/%"),
            ).fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        conn.close()




app = create_app()
