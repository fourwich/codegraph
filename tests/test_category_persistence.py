"""Category must survive every decision read path (including line links)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from codegraph.models import CodeNode, Decision, DecisionSource, DecisionStatus
from codegraph.storage import (
    connect,
    db_path_for_root,
    init_schema,
    insert_decision_links,
    insert_decisions,
    insert_nodes,
    query_all_decisions,
    query_decisions_for_line_links,
    query_decisions_for_node_lines,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _decision(uid: str, category: str, content: str) -> Decision:
    decision = Decision(
        uid=uid,
        content=content,
        reason="",
        status=DecisionStatus.ACCEPTED,
        source=DecisionSource.COMMIT,
        source_ref="commit abc",
        timestamp=NOW,
        file_path="lib/x.js",
        line=None,
    )
    decision.category = category
    return decision


def test_category_roundtrip_through_links(tmp_path: Path) -> None:
    """A dependency decision read via decision_code_links stays 'dependency'."""
    conn = connect(db_path_for_root(tmp_path))
    try:
        init_schema(conn)
        insert_nodes(
            conn,
            [
                CodeNode(
                    uid="n1",
                    kind="function",
                    name="f",
                    file_path="lib/x.js",
                    line_start=1,
                    line_end=20,
                    language="javascript",
                )
            ],
        )
        insert_decisions(
            conn,
            [
                _decision("dep1", "dependency", "bump qs from 6.5.2 to 6.5.3"),
                _decision("des1", "design", "use a cached slice because of cost"),
            ],
        )
        insert_decision_links(
            conn,
            [
                ("dep1", "n1", "lib/x.js", 10),
                ("des1", "n1", "lib/x.js", 11),
            ],
        )

        by_line = query_decisions_for_line_links(conn, "lib/x.js", 10)
        assert [d.uid for d in by_line] == ["dep1"]
        assert by_line[0].category == "dependency"

        by_range = query_decisions_for_node_lines(conn, "lib/x.js", 1, 20)
        assert {d.uid: d.category for d in by_range} == {
            "dep1": "dependency",
            "des1": "design",
        }

        everything = {d.uid: d.category for d in query_all_decisions(conn)}
        assert everything == {"dep1": "dependency", "des1": "design"}
    finally:
        conn.close()
