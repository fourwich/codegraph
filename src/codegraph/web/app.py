"""FastAPI app serving the CodeGraph web UI and JSON APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from codegraph.commands.why import decision_from_dgraph
from codegraph.models import Decision, normalize_location_path
from codegraph.storage import (
    connect,
    count_edges_at,
    db_path_for_root,
    query_all_decisions,
    query_decisions_for_file,
    query_decisions_for_line,
    query_nodes_at,
)

STATIC_DIR = Path(__file__).parent / "static"


def _sqlite_path() -> Path:
    return db_path_for_root(Path.cwd())


def _load_graph_sqlite(at: datetime, scope: str) -> dict[str, Any]:
    """Load nodes/edges/decisions valid at a timestamp."""
    db_path = _sqlite_path()
    if not db_path.exists():
        return {"nodes": [], "edges": [], "decisions": [], "stats": _empty_stats()}
    conn = connect(db_path)
    try:
        nodes = query_nodes_at(conn, at, scope)
        edge_count = count_edges_at(conn, at, scope)
        decisions = [d for d in query_all_decisions(conn) if d.timestamp.date() <= at.date()]
        prefix = normalize_location_path(scope)
        if prefix and prefix != ".":
            decisions = [d for d in decisions if (d.file_path or "").startswith(prefix)]
        return {
            "nodes": [_node_json(n) for n in nodes],
            "edges": [],
            "decisions": [_decision_json(d) for d in decisions[:50]],
            "stats": {
                "nodes": len(nodes),
                "edges": edge_count,
                "decisions": len(decisions),
            },
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
        backend: str = Query(default="sqlite"),
    ) -> JSONResponse:
        """Return graph payload valid at a date."""
        date = _parse_date(at)
        if backend == "dgraph":
            data = _load_graph_dgraph(date, scope)
        else:
            data = _load_graph_sqlite(date, scope)
        return JSONResponse(data)

    @app.get("/api/why")
    def api_why(
        file: str = Query(...),
        line: int = Query(...),
        backend: str = Query(default="sqlite"),
    ) -> JSONResponse:
        """Return node + decisions for a file:line."""
        path = normalize_location_path(file)
        node = None
        decisions: list[Decision] = []
        if backend == "dgraph":
            from codegraph.graph import DgraphClient, DgraphConnectionError

            try:
                client = DgraphClient()
                raw_node = client.query_node_at(path, line)
                raw_decisions = client.query_decisions_for(path, line)
                client.close()
            except DgraphConnectionError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            decisions = [decision_from_dgraph(item) for item in raw_decisions]
            node = raw_node
        else:
            db_path = _sqlite_path()
            if db_path.exists():
                conn = connect(db_path)
                try:
                    from codegraph.storage import find_node_at_line

                    found = find_node_at_line(conn, path, line)
                    node = _node_json(found) if found else None
                    decisions = query_decisions_for_line(conn, path, line)
                    if not decisions:
                        decisions = query_decisions_for_file(conn, path)
                finally:
                    conn.close()
        return JSONResponse(
            {
                "file": path,
                "line": line,
                "node": node,
                "decisions": [_decision_json(d) for d in decisions[:10]],
            }
        )

    @app.get("/api/decisions")
    def api_decisions(
        file: str = Query(default=""),
        backend: str = Query(default="sqlite"),
    ) -> JSONResponse:
        """Return decision timeline for a file or all decisions."""
        if backend == "dgraph":
            from codegraph.graph import DgraphClient, DgraphConnectionError

            try:
                client = DgraphClient()
                raw = client.query_all_decisions()
                client.close()
            except DgraphConnectionError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            decisions = [decision_from_dgraph(item) for item in raw]
        else:
            db_path = _sqlite_path()
            decisions = []
            if db_path.exists():
                conn = connect(db_path)
                try:
                    decisions = (
                        query_decisions_for_file(conn, normalize_location_path(file))
                        if file
                        else query_all_decisions(conn)
                    )
                finally:
                    conn.close()
        return JSONResponse({"decisions": [_decision_json(d) for d in decisions]})

    @app.get("/api/timeline")
    def api_timeline(
        scope: str = Query(default="."),
        backend: str = Query(default="sqlite"),
    ) -> JSONResponse:
        """Return commit-ish date ticks for the time slider."""
        ticks = _timeline_sqlite(scope)
        return JSONResponse({"ticks": ticks})

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
    """Collect distinct valid_from dates as slider ticks."""
    db_path = _sqlite_path()
    if not db_path.exists():
        return []
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT substr(valid_from, 1, 10) AS d FROM nodes "
            "WHERE valid_from IS NOT NULL ORDER BY d"
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        conn.close()


def _load_graph_dgraph(at: datetime, scope: str) -> dict[str, Any]:
    """Load graph payload from Dgraph."""
    from codegraph.graph import DgraphClient, DgraphConnectionError

    try:
        client = DgraphClient()
        payload = client.query_graph_at(at.date().isoformat(), scope)
        raw_decisions = client.query_all_decisions()
        client.close()
    except DgraphConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    nodes = [
        {
            "uid": n.get("node_uid") or n.get("uid"),
            "kind": n.get("kind"),
            "name": n.get("name"),
            "file_path": n.get("file_path"),
            "line_start": n.get("line_start"),
            "line_end": n.get("line_end"),
            "language": n.get("language", ""),
            "commit_sha": n.get("commit_sha", ""),
        }
        for n in payload.get("nodes") or []
    ]
    decisions = [decision_from_dgraph(item) for item in raw_decisions]
    return {
        "nodes": nodes,
        "edges": [],
        "decisions": [_decision_json(d) for d in decisions[:50]],
        "stats": {
            "nodes": len(nodes),
            "edges": int(payload.get("edge_count") or 0),
            "decisions": int(payload.get("decision_count") or 0),
        },
    }


app = create_app()
