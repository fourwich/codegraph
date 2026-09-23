"""SQLite graph store: node and edge persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from codegraph.models import CodeNode, Edge

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
  parent_uid TEXT
);
CREATE TABLE IF NOT EXISTS edges (
  from_uid TEXT,
  to_uid TEXT,
  kind TEXT,
  file_path TEXT,
  line INT
);
"""


def db_path_for_root(root: Path) -> Path:
    """Return graph.db path under the repository root."""
    return root / DEFAULT_DB_REL


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (and create if needed) the SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables when missing."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def clear_graph(conn: sqlite3.Connection) -> None:
    """Delete existing graph rows before a full rebuild."""
    conn.execute("DELETE FROM edges")
    conn.execute("DELETE FROM nodes")
    conn.commit()


def insert_nodes(conn: sqlite3.Connection, nodes: list[CodeNode]) -> None:
    """Bulk insert nodes."""
    conn.executemany(
        "INSERT OR REPLACE INTO nodes "
        "(uid, kind, name, file_path, line_start, line_end, language, parent_uid) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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


def count_nodes(conn: sqlite3.Connection) -> int:
    """Count stored nodes."""
    row = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()
    return int(row[0]) if row else 0


def count_edges(conn: sqlite3.Connection) -> int:
    """Count stored edges."""
    row = conn.execute("SELECT COUNT(*) FROM edges").fetchone()
    return int(row[0]) if row else 0


def find_node_at_line(conn: sqlite3.Connection, file_path: str, line: int) -> CodeNode | None:
    """Return the innermost CodeNode covering file:line."""
    rows = conn.execute(
        "SELECT uid, kind, name, file_path, line_start, line_end, language, parent_uid "
        "FROM nodes WHERE file_path = ? AND line_start <= ? AND line_end >= ? "
        "ORDER BY (line_end - line_start) ASC LIMIT 1",
        (file_path, line, line),
    ).fetchall()
    if not rows:
        return None
    uid, kind, name, path, line_start, line_end, language, parent_uid = rows[0]
    return CodeNode(
        uid=uid,
        kind=kind,
        name=name,
        file_path=path,
        line_start=line_start,
        line_end=line_end,
        language=language,
        parent_uid=parent_uid,
    )
