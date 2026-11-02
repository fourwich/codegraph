"""The edge table stores relationships, not call sites.

A function that calls `format` fifty times produced fifty identical
(from_uid, to_uid, kind) rows. Measured across five repositories, 6-12% of all
edge rows were such duplicates — on fmt a single template helper held 1026 rows
pointing at 18 targets — which inflates every reported edge total.
"""

from __future__ import annotations

from codegraph.models import Edge
from codegraph.storage import connect, db_path_for_root, init_schema, insert_edges


def _db(tmp_path):
    conn = connect(db_path_for_root(tmp_path))
    init_schema(conn)
    return conn


def _edge(source: str, target: str, kind: str = "uses", line: int = 1) -> Edge:
    return Edge(from_uid=source, to_uid=target, kind=kind, file_path="src/a.py", line=line)


def test_duplicate_edges_collapse_to_one_row(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        insert_edges(conn, [_edge("a", "b"), _edge("a", "b"), _edge("a", "b")])
        count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    finally:
        conn.close()

    assert count == 1


def test_same_pair_different_kind_stays_separate(tmp_path) -> None:
    """`contains` and `uses` are different relationships between the same nodes."""
    conn = _db(tmp_path)
    try:
        insert_edges(conn, [_edge("a", "b", "uses"), _edge("a", "b", "contains")])
        count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    finally:
        conn.close()

    assert count == 2


def test_different_pairs_all_survive(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        insert_edges(conn, [_edge("a", "b"), _edge("a", "c"), _edge("d", "b")])
        count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    finally:
        conn.close()

    assert count == 3


def test_first_observation_keeps_its_location(tmp_path) -> None:
    """The kept row records where the edge was first seen."""
    conn = _db(tmp_path)
    try:
        insert_edges(conn, [_edge("a", "b", line=42), _edge("a", "b", line=99)])
        line = conn.execute("SELECT line FROM edges").fetchone()[0]
    finally:
        conn.close()

    assert line == 42


def test_empty_list_is_safe(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        insert_edges(conn, [])
        count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    finally:
        conn.close()

    assert count == 0
