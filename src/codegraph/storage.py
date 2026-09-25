"""SQLite graph store: nodes, edges, and decisions persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from codegraph.models import CodeNode, Decision, Edge

DEFAULT_DB_REL = Path(".codegraph") / "graph.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
  uid TEXT PRIMARY KEY,
  kind TEXT,
  name TEXT,
  file_path TEXT,
  line_start INT,
  line_end INT,
  language TEXT,
  parent_uid TEXT,
  valid_from TEXT,
  valid_to TEXT,
  commit_sha TEXT
);
CREATE TABLE IF NOT EXISTS edges (
  from_uid TEXT,
  to_uid TEXT,
  kind TEXT,
  file_path TEXT,
  line INT
);
CREATE TABLE IF NOT EXISTS decisions (
  uid TEXT PRIMARY KEY,
  content TEXT,
  reason TEXT,
  alternatives TEXT,
  status TEXT,
  source TEXT,
  source_ref TEXT,
  timestamp TEXT,
  author TEXT,
  file_path TEXT,
  line INT,
  constraints TEXT,
  confidence REAL
);
"""

# Columns added when upgrading older local DBs
_NODE_MIGRATIONS = (
    ("valid_from", "TEXT"),
    ("valid_to", "TEXT"),
    ("commit_sha", "TEXT"),
)


def db_path_for_root(root: Path) -> Path:
    """Return graph.db path under the repository root."""
    return root / DEFAULT_DB_REL


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (and create if needed) the SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and apply lightweight migrations."""
    conn.executescript(SCHEMA_SQL)
    _migrate_nodes(conn)
    conn.commit()


def _migrate_nodes(conn: sqlite3.Connection) -> None:
    """Add missing columns on older nodes tables."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(nodes)")}
    for name, coltype in _NODE_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE nodes ADD COLUMN {name} {coltype}")


def clear_graph(conn: sqlite3.Connection) -> None:
    """Delete existing graph rows before a full rebuild."""
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM nodes")
    conn.execute("DELETE FROM decisions")
    conn.commit()


def _dt(value: datetime | None) -> str | None:
    """Serialize datetime for SQLite storage."""
    return value.isoformat() if value else None


def insert_nodes(conn: sqlite3.Connection, nodes: list[CodeNode]) -> None:
    """Bulk insert node versions."""
    conn.executemany(
        "INSERT OR REPLACE INTO nodes "
        "(uid, kind, name, file_path, line_start, line_end, language, parent_uid, "
        "valid_from, valid_to, commit_sha) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                n.uid,
                n.kind,
                n.name,
                n.file_path,
                n.line_start,
                n.line_end,
                n.language,
                n.parent_uid,
                _dt(n.valid_from),
                _dt(n.valid_to),
                n.commit_sha,
            )
            for n in nodes
        ],
    )
    conn.commit()


def insert_edges(conn: sqlite3.Connection, edges: list[Edge]) -> None:
    """Bulk insert edges."""
    conn.executemany(
        "INSERT INTO edges (from_uid, to_uid, kind, file_path, line) VALUES (?, ?, ?, ?, ?)",
        [(e.from_uid, e.to_uid, e.kind, e.file_path, e.line) for e in edges],
    )
    conn.commit()


def insert_decisions(conn: sqlite3.Connection, decisions: list[Decision]) -> None:
    """Bulk insert extracted decisions."""
    conn.executemany(
        "INSERT OR REPLACE INTO decisions "
        "(uid, content, reason, alternatives, status, source, source_ref, timestamp, "
        "author, file_path, line, constraints, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                d.uid,
                d.content,
                d.reason,
                json.dumps(d.alternatives, ensure_ascii=False),
                d.status.value,
                d.source.value,
                d.source_ref,
                d.timestamp.isoformat(),
                d.author,
                d.file_path,
                d.line,
                json.dumps(d.constraints, ensure_ascii=False),
                d.confidence,
            )
            for d in decisions
        ],
    )
    conn.commit()


def count_nodes(conn: sqlite3.Connection) -> int:
    """Count stored node versions."""
    row = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()
    return int(row[0]) if row else 0


def count_edges(conn: sqlite3.Connection) -> int:
    """Count stored edges."""
    row = conn.execute("SELECT COUNT(*) FROM edges").fetchone()
    return int(row[0]) if row else 0


def count_decisions(conn: sqlite3.Connection) -> int:
    """Count stored decisions."""
    row = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
    return int(row[0]) if row else 0


def _row_to_node(row: tuple) -> CodeNode:
    """Map a nodes row to CodeNode."""
    (
        uid,
        kind,
        name,
        path,
        line_start,
        line_end,
        language,
        parent_uid,
        valid_from,
        valid_to,
        commit_sha,
    ) = row
    return CodeNode(
        uid=uid,
        kind=kind,
        name=name,
        file_path=path,
        line_start=line_start,
        line_end=line_end,
        language=language,
        parent_uid=parent_uid,
        valid_from=datetime.fromisoformat(valid_from) if valid_from else datetime.fromtimestamp(0),
        valid_to=datetime.fromisoformat(valid_to) if valid_to else None,
        commit_sha=commit_sha or "",
    )


def find_node_at_line(conn: sqlite3.Connection, file_path: str, line: int) -> CodeNode | None:
    """Return the innermost CodeNode covering file:line (latest version)."""
    rows = conn.execute(
        "SELECT uid, kind, name, file_path, line_start, line_end, language, parent_uid, "
        "valid_from, valid_to, commit_sha "
        "FROM nodes WHERE file_path = ? AND line_start <= ? AND line_end >= ? "
        "ORDER BY (line_end - line_start) ASC, valid_from DESC LIMIT 1",
        (file_path, line, line),
    ).fetchall()
    if not rows:
        return None
    return _row_to_node(rows[0])


def query_nodes_at(conn: sqlite3.Connection, at: datetime, scope: str) -> list[CodeNode]:
    """Return nodes valid at a timestamp, filtered by file_path prefix."""
    prefix = (scope or "").replace("\\", "/").rstrip("/")
    sql = (
        "SELECT uid, kind, name, file_path, line_start, line_end, language, parent_uid, "
        "valid_from, valid_to, commit_sha FROM nodes "
        "WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to >= ?) "
    )
    params: list[object] = [at.isoformat(), at.isoformat()]
    if prefix and prefix != ".":
        sql += "AND file_path LIKE ? "
        params.append(prefix + "%")
    sql += "ORDER BY file_path, line_start"
    return [_row_to_node(row) for row in conn.execute(sql, params).fetchall()]


def count_edges_at(conn: sqlite3.Connection, at: datetime, scope: str = "") -> int:
    """Count edges whose both endpoints are valid at the given timestamp.

    Scope filters edges by the source node's file_path prefix.
    """
    prefix = (scope or "").replace("\\", "/").rstrip("/")
    sql = """
    SELECT COUNT(*) FROM edges e
    WHERE EXISTS (
      SELECT 1 FROM nodes n_from
      WHERE n_from.uid = e.from_uid
        AND n_from.valid_from <= ?
        AND (n_from.valid_to IS NULL OR n_from.valid_to >= ?)
    ) AND EXISTS (
      SELECT 1 FROM nodes n_to
      WHERE n_to.uid = e.to_uid
        AND n_to.valid_from <= ?
        AND (n_to.valid_to IS NULL OR n_to.valid_to >= ?)
    )
    """
    params: list[object] = [at.isoformat(), at.isoformat(), at.isoformat(), at.isoformat()]
    if prefix and prefix != ".":
        sql += " AND e.file_path LIKE ? "
        params.append(prefix + "%")
    row = conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def query_decisions_for_line(conn: sqlite3.Connection, file_path: str, line: int) -> list[Decision]:
    """Return decisions bound to file:line only (strict line match)."""
    rows = conn.execute(
        "SELECT uid, content, reason, alternatives, status, source, source_ref, timestamp, "
        "author, file_path, line, constraints, confidence FROM decisions "
        "WHERE file_path = ? AND line = ? "
        "ORDER BY timestamp DESC LIMIT 20",
        (file_path, line),
    ).fetchall()
    return [_row_to_decision(row) for row in rows]


def query_decisions_for_file(conn: sqlite3.Connection, file_path: str) -> list[Decision]:
    """Return decisions whose file_path equals this file (any line)."""
    prefix = file_path.replace("\\", "/")
    rows = conn.execute(
        "SELECT uid, content, reason, alternatives, status, source, source_ref, timestamp, "
        "author, file_path, line, constraints, confidence FROM decisions "
        "WHERE file_path = ? "
        "ORDER BY timestamp DESC LIMIT 20",
        (prefix,),
    ).fetchall()
    return [_row_to_decision(row) for row in rows]


def query_decisions_for_dir(conn: sqlite3.Connection, file_path: str, limit: int = 5) -> list[Decision]:
    """Return decisions under the file's directory prefix (file-level fallback)."""
    path = file_path.replace("\\", "/")
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    if not parent:
        return query_all_decisions(conn)[:limit]
    rows = conn.execute(
        "SELECT uid, content, reason, alternatives, status, source, source_ref, timestamp, "
        "author, file_path, line, constraints, confidence FROM decisions "
        "WHERE file_path = ? OR file_path LIKE ? "
        "ORDER BY timestamp DESC LIMIT ?",
        (parent, parent + "/%", limit),
    ).fetchall()
    return [_row_to_decision(row) for row in rows]


def query_decisions_for_commit(conn: sqlite3.Connection, commit_sha: str) -> list[Decision]:
    """Return decisions whose source_ref mentions this commit sha."""
    if not commit_sha:
        return []
    short = commit_sha[:10]
    rows = conn.execute(
        "SELECT uid, content, reason, alternatives, status, source, source_ref, timestamp, "
        "author, file_path, line, constraints, confidence FROM decisions "
        "WHERE source_ref LIKE ? OR source_ref LIKE ? "
        "ORDER BY timestamp DESC LIMIT 10",
        (f"%{commit_sha}%", f"%{short}%"),
    ).fetchall()
    return [_row_to_decision(row) for row in rows]


def query_all_decisions(conn: sqlite3.Connection) -> list[Decision]:
    """Return all stored decisions."""
    rows = conn.execute(
        "SELECT uid, content, reason, alternatives, status, source, source_ref, timestamp, "
        "author, file_path, line, constraints, confidence FROM decisions "
        "ORDER BY timestamp ASC"
    ).fetchall()
    return [_row_to_decision(row) for row in rows]


def _row_to_decision(row: tuple) -> Decision:
    """Map a decisions row to Decision."""
    from codegraph.models import DecisionSource, DecisionStatus

    (
        uid,
        content,
        reason,
        alternatives,
        status,
        source,
        source_ref,
        timestamp,
        author,
        file_path,
        line,
        constraints,
        confidence,
    ) = row
    status_val = status if status in DecisionStatus._value2member_map_ else "accepted"
    source_val = source if source in DecisionSource._value2member_map_ else "commit"
    return Decision(
        uid=uid,
        content=content or "",
        reason=reason or "",
        alternatives=json.loads(alternatives or "[]"),
        status=DecisionStatus(status_val),
        source=DecisionSource(source_val),
        source_ref=source_ref or "",
        timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.fromtimestamp(0),
        author=author or "",
        file_path=file_path or "",
        line=line,
        constraints=json.loads(constraints or "[]"),
        confidence=float(confidence or 0.5),
    )
