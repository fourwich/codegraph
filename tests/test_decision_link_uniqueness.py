"""Binding a decision to two nodes that start on the same line must not crash.

`decision_code_links` is unique on (decision_uid, file_path, line). A class and its
first method can share a start line, and a decision that mentions both produced two
rows for that line — an IntegrityError that aborted the whole index run on a real
repository.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from codegraph.models import DecisionSource, DecisionStatus, DecisionTier
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    query_decisions_for_line_links,
)


def _db(tmp_path):
    conn = connect(db_path_for_root(tmp_path))
    init_schema(conn)
    return conn


def test_duplicate_line_links_are_collapsed(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        insert_decision_links(
            conn,
            [
                ("d1", "node-class", "src/app.py", 10),
                ("d1", "node-method", "src/app.py", 10),
            ],
        )
        rows = conn.execute(
            "SELECT decision_uid, node_uid, file_path, line FROM decision_code_links"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0][1] == "node-class"


def test_the_same_link_twice_is_collapsed(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        insert_decision_links(
            conn,
            [("d1", "n1", "src/app.py", 3), ("d1", "n1", "src/app.py", 3)],
        )
        count = conn.execute("SELECT COUNT(*) FROM decision_code_links").fetchone()[0]
    finally:
        conn.close()

    assert count == 1


def test_different_lines_are_all_kept(tmp_path) -> None:
    conn = _db(tmp_path)
    try:
        insert_decision_links(
            conn,
            [
                ("d1", "n1", "src/app.py", 3),
                ("d1", "n2", "src/app.py", 9),
                ("d2", "n1", "src/app.py", 3),
            ],
        )
        count = conn.execute("SELECT COUNT(*) FROM decision_code_links").fetchone()[0]
    finally:
        conn.close()

    assert count == 3


def test_a_line_still_answers_after_collapsing(tmp_path) -> None:
    """The surviving row is what `why` reads, so it has to be queryable."""
    conn = _db(tmp_path)
    try:
        conn.execute(
            "INSERT INTO decisions (uid, content, reason, alternatives, status, source, "
            "source_ref, timestamp, author, file_path, line, constraints, confidence, "
            "category, tier) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "d1",
                "Use SQLite because it is embedded",
                "",
                "[]",
                DecisionStatus.ACCEPTED.value,
                DecisionSource.ADR.value,
                "ADR 001",
                datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                "",
                "docs/adr/001.md",
                None,
                "[]",
                0.8,
                "design",
                DecisionTier.DECISION.value,
            ),
        )
        insert_decision_links(
            conn,
            [("d1", "node-class", "src/app.py", 10), ("d1", "node-method", "src/app.py", 10)],
        )
        found = query_decisions_for_line_links(conn, "src/app.py", 10)
    finally:
        conn.close()

    assert [d.uid for d in found] == ["d1"]


def test_integrity_error_is_not_raised_for_the_old_shape() -> None:
    """Guard: the constraint this test protects still exists."""
    with pytest.raises(sqlite3.IntegrityError):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(
                "CREATE TABLE t (a TEXT, b TEXT, c TEXT, d INT, "
                "UNIQUE(a, c, d))"
            )
            conn.execute("INSERT INTO t VALUES ('d1','n1','f',1)")
            conn.execute("INSERT INTO t VALUES ('d1','n2','f',1)")
        finally:
            conn.close()
